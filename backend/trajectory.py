"""Layer 5 (종단 궤적 예측) — '데이터 기반 미래 예측'.

핵심 아이디어: 단일 예측값이나 AI 추정이 아니라, '너와 비슷한 사람들'을 KLIPS 패널의
시작 시점에서 찾아 **같은 사람들을 앞으로 추적**해, 향후 N년의 소득·이직 궤적을
분위수(p25/50/75) 분포로 보여준다.

  · 실제 관측된 경로 → "AI가 지어낸 미래" 아님
  · 단일값이 아닌 분포(범위) → 예측 불확실성을 정직하게 노출
  · 뒤 연차일수록 추적 표본(sample_n)이 줄어 신뢰도 하락 → 그 수치도 함께 반환

KLIPS(12~27차, 2009~2024) 사용. 원본이 없으면 빈 리스트 반환(엔진은 정상 동작).
"""

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from config import settings

KLIPS_PATH = settings.data_abspath / "raw" / "klips" / "klips_base.pkl"
YP_PATH = settings.data_abspath / "clean" / "yp_clean.csv"
BUILD_REPORT_PATH = KLIPS_PATH.parent / "klips_build_report.json"


@lru_cache(maxsize=1)
def wage_basis() -> dict:
    """소득 궤적의 화폐 기준 — 전처리 빌드 리포트에서 읽는다.

    `월임금_실질` 은 preprocess_klips.py 가 CPI 로 디플레이트한 값이다. 어느 연도
    기준인지 응답에 같이 실어야 "5년 뒤 400만원" 을 명목으로 오독하지 않는다.
    리포트가 없으면(구 빌드) 기준을 모른다고 정직하게 알린다.
    """
    if not BUILD_REPORT_PATH.exists():
        return {"deflated": False, "base_year": None,
                "label": "명목(기준연도 미상 — klips_build_report.json 없음)"}
    try:
        r = json.loads(BUILD_REPORT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"deflated": False, "base_year": None, "label": "기준 불명"}
    if not r.get("deflated"):
        return {"deflated": False, "base_year": None, "label": "명목(디플레이트 안 됨)"}
    y = r.get("cpi_base_year")
    return {"deflated": True, "base_year": y, "years": r.get("years"),
            "label": f"{y}년 기준 실질"}


SATIS = ["satis_work", "satis_growth", "satis_income", "satis_stability", "satis_future"]
YP_FEATS = ["age", "sex", "income_now", "edu_level"]
REQUIRED_COLS = ["pid", "wave", "나이", "성별", "학력", "월임금_실질", "이직"]

# ---------------------------------------------------------------- 매칭 설계
# 예전엔 나이·성별·임금·학력 4개만 z-score 유클리드로 썼다. 그런데 패널에 이미 있는
# **직종이 임금 분산의 36.8%** 를 설명한다(나이 17.8%, 학력 18.6%). 근속기간 21.5%,
# 종업원규모 17.8% 도 마찬가지로 놀고 있었다. 넣지 않을 이유가 없었다.
#
# 다만 직종은 KSCO 3자리 코드라 **숫자로 거리를 재면 안 된다**(111 과 992 의 '차이
# 881' 은 아무 의미가 없다). 처음엔 대/중/소분류 계층 일치도로 페널티를 줬는데,
# hold-out 평가에서 오히려 MAE 가 16% 나빠졌다 — 직종을 맞추느라 소득이 비슷한
# 이웃을 버렸기 때문이다(현재 소득이 미래 소득의 가장 강한 예측자다).
# → **직종별 평균 로그임금(목적변수 인코딩)** 으로 바꿔 '직종의 소득 수준' 이라는
#   순서 있는 축 하나로 만든다. 표본이 적은 직종은 전체 평균 쪽으로 축소(smoothing).
#
# 가중치 단위는 전부 'z-거리' 로 통일한다. 범주형 불일치는 '몇 σ 만큼 다른가' 로 환산.
# 값은 손으로 정하지 않고 scripts/eval_matching.py --tune 로 탐색해 넣는다.
NUM_FEATS = {          # z-score 후 가중 유클리드 (가중치 = z 배율)
    "나이": 1.5,
    "월임금_실질": 2.0,     # 현재 소득이 미래 소득의 가장 강한 예측자 — 가장 무겁다
    "학력": 0.3,
    "종업원규모": 0.3,
    # 근속은 나이·소득과 거의 겹쳐서 탐색에서 0 이 됐다(넣으면 오히려 나빠짐).
    # 컬럼·입력 배관은 남겨 두되 가중치 0 으로 꺼 둔다 — 재탐색으로 되살릴 수 있게.
    "근속기간_log": 0.0,
    "직종소득지수": 0.3,
}
CAT_PENALTY = {        # 값이 다를 때 더해지는 z-거리
    "성별": 2.0,
    "정규여부": 1.2,
}
OCC_SMOOTH = 50.0      # 직종 목적변수 인코딩의 축소 강도(관측 수 기준 prior 가중)
# 후보 쪽 값이 결측일 때의 중립 거리. 중앙값으로 채우면 '결측인 사람' 이 중앙값
# 질의에 대해 완벽히 일치하는 것으로 둔갑한다 → 일치도 불일치도 아닌 값을 준다.
MISSING_Z = 1.0

# 요청(Profile) 키 → 패널 컬럼. 요청에 없는 항목은 **거리 계산에서 아예 뺀다**
# (중앙값으로 채우면 그 축에서 모두가 '중간 사람' 과 가까워져 매칭이 중앙으로 쏠린다).
FEATURE_SOURCE = {
    "나이": "age",
    "성별": "sex",
    "월임금_실질": "monthly_wage",
    "학력": "edu_level",
    "종업원규모": "firm_size",
    "근속기간_log": "tenure_years",
    "정규여부": "is_regular",
    "직종소득지수": "job_category",     # 코드 → 직종별 평균 로그임금으로 변환해 쓴다
}


@lru_cache(maxsize=1)
def _panel():
    if not KLIPS_PATH.exists():
        return None
    raw = pd.read_pickle(KLIPS_PATH)
    if [c for c in REQUIRED_COLS if c not in raw.columns]:
        return None  # 필수 컬럼이 없는 빌드 → 궤적 생략(엔진은 계속 동작)

    opt = [c for c in ("종사상지위", "직종", "종업원규모", "근속기간")
           if c in raw.columns]
    b = raw[REQUIRED_COLS + opt].copy()
    b = b[b["월임금_실질"] > 0].dropna(subset=["나이", "성별", "월임금_실질"])
    b["학력"] = b["학력"].fillna(b["학력"].median())
    b["이직"] = pd.to_numeric(b["이직"], errors="coerce").fillna(0)

    if "종사상지위" in b.columns:
        # 고용형태 → 정규여부 (상용1=정규, 임시2·일용3=비정규). 임금 관측 행은
        # 종사상지위가 1~3 뿐이라(자영은 임금 문항 무응답) 사실상 전부 채워진다.
        st = pd.to_numeric(b["종사상지위"], errors="coerce")
        b["정규여부"] = np.where(st == 1, 1.0, np.where(st.isin([2, 3]), 2.0, np.nan))
    if "근속기간" in b.columns:
        b["근속기간_log"] = np.log1p(pd.to_numeric(b["근속기간"], errors="coerce"))

    occ_map: dict = {}
    if "직종" in b.columns:
        # 직종 → 평균 로그임금. 표본이 적은 직종은 전체 평균으로 축소해
        # 몇 명뿐인 직종이 극단값을 갖는 걸 막는다.
        lw = np.log(b["월임금_실질"])
        grp = lw.groupby(b["직종"])
        cnt, mean = grp.count(), grp.mean()
        prior = float(lw.mean())
        enc = (cnt * mean + OCC_SMOOTH * prior) / (cnt + OCC_SMOOTH)
        occ_map = {float(k): float(v) for k, v in enc.items()}
        b["직종소득지수"] = b["직종"].map(occ_map)

    num = [c for c in NUM_FEATS if c in b.columns]
    mu, sd = b[num].mean(), b[num].std().replace(0, 1)
    return {"b": b, "mu": mu, "sd": sd, "num": num,
            "cat": [c for c in CAT_PENALTY if c in b.columns],
            "occ_map": occ_map, "occ_prior": float(np.log(b["월임금_실질"]).mean())}


def _query_vector(features: dict, P: dict) -> dict:
    """요청 → 매칭에 실제로 쓸 값만. 없는 항목은 넣지 않는다(= 그 축은 거리에서 제외)."""
    q: dict = {}
    for col, key in FEATURE_SOURCE.items():
        v = features.get(key)
        if v is None:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if col == "근속기간_log":
            v = float(np.log1p(max(v, 0.0)))
        elif col == "직종소득지수":
            # 모르는 직종 코드는 매칭에서 제외한다(전체 평균을 넣으면 '평균 직종'
            # 이라는 없는 사람과 가까워진다).
            enc = P["occ_map"].get(float(v)) if P else None
            if enc is None:
                continue
            v = enc
        q[col] = v
    return q


def _match_distance(cand: pd.DataFrame, q: dict, P: dict) -> np.ndarray:
    """혼합형(수치+범주) 거리. 전부 z-거리 단위로 환산해 유클리드로 합친다."""
    mu, sd = P["mu"], P["sd"]
    d2 = np.zeros(len(cand), dtype=float)

    for col, w in NUM_FEATS.items():
        if col not in q or col not in P["num"]:
            continue
        z = (cand[col].to_numpy(dtype=float) - mu[col]) / sd[col]
        dz = np.abs(z - (q[col] - mu[col]) / sd[col])
        dz = np.where(np.isnan(dz), MISSING_Z, dz)
        d2 += (w * dz) ** 2

    for col, pen in CAT_PENALTY.items():
        if col not in q or col not in P["cat"]:
            continue
        v = cand[col].to_numpy(dtype=float)
        diff = np.where(np.isnan(v), MISSING_Z, np.where(v == q[col], 0.0, pen))
        d2 += diff ** 2

    return np.sqrt(d2)


def matched_features(features: dict) -> list[str]:
    """이 요청이 실제로 매칭에 쓴 항목 — 개인화 깊이를 응답에 밝히기 위한 것."""
    P = _panel()
    return sorted(_query_vector(features, P)) if P else []


def project_trajectory(features: dict, horizon: int = 15, k: int = 300,
                       min_n: int = 15) -> list[dict]:
    """프로필 → 향후 `horizon`년 소득·이직 궤적(분위수)."""
    P = _panel()
    if P is None:
        return []
    b = P["b"]

    A = features.get("age")
    if A is None:
        return []
    q = _query_vector(features, P)
    if "월임금_실질" not in q:
        # 소득 미입력 → 같은 나이대 중앙값으로 대신 잡는다(매칭 축 자체는 유지)
        near = b[b["나이"].between(A - 1, A + 1)]["월임금_실질"]
        q["월임금_실질"] = float(near.median()) if len(near) else \
            float(b["월임금_실질"].median())

    # 시작 후보: 시작 나이 ±1
    cand = b[b["나이"].between(A - 1, A + 1)]
    if len(cand) < min_n:
        return []
    dist = _match_distance(cand, q, P)
    starts = (cand.assign(_d=dist).nsmallest(k, "_d")[["pid", "wave"]]
              .rename(columns={"wave": "start_wave"}).reset_index(drop=True))
    starts["start_id"] = np.arange(len(starts))
    followed = starts.merge(
        b[["pid", "wave", "월임금_실질", "이직"]], on="pid", how="left"
    )
    followed["year_from_start"] = followed["wave"] - followed["start_wave"]
    followed = followed[followed["year_from_start"].between(0, horizon)]

    out = []
    for h in range(horizon + 1):
        incs = followed.loc[followed["year_from_start"] == h, "월임금_실질"].to_numpy()
        seg = followed[(followed["year_from_start"] > 0) &
                       (followed["year_from_start"] <= h)]
        moved_by_start = seg.groupby("start_id")["이직"].max() if len(seg) else []
        tot = len(moved_by_start)
        moved = int(np.sum(moved_by_start)) if tot else 0
        if len(incs) >= min_n:
            out.append({
                "year": h, "age": int(A) + h, "sample_n": len(incs),
                "income_p25": int(np.percentile(incs, 25)),
                "income_p50": int(np.percentile(incs, 50)),
                "income_p75": int(np.percentile(incs, 75)),
                "job_change_cum": round(moved / tot, 3) if tot else None,
            })
    return out


# ---------------------------------------------------------------- 만족도 궤적 (YP)
# 선택(A/B)별 만족도 분기용 이벤트 정의.
#   기존엔 만족도 궤적이 '프로필 기준' 하나뿐이라 A와 B가 **같은 값**이었다
#   (compare.py 가 그 사실을 주석으로 인정하고 있었다). 평행우주 비교의 3주인공
#   중 하나가 비교를 못 하고 있던 셈. YP 패널에서 '실제로 그 선택을 한 사람'만
#   추려서 따라가면 관측만으로 분기시킬 수 있다.
#   ※ 이건 인과효과가 아니라 **조건부 관측 경로**다. 선택한 사람과 안 한 사람은
#     애초에 다를 수 있다(자기선택). 응답의 source 에 그대로 적어 내보낸다.
YP_EVENTS = {
    "move": "이직",        # changed_job == 1
    "stay": "유지",        # 관측 구간 내 이직 없음
    "startup": "창업",     # 비임금(자영) 소득 응답 발생
    "enroll": "진학",      # 학력코드 상승
}
MIN_BRANCH_N = 30          # 분기 하위집단이 이보다 작으면 분기하지 않는다
MAX_WIDEN = 4              # 표본 확보용 이웃 확대 상한(k 의 배수). 넘으면 분기 포기

# 학력 코드계 변환: 요청(Profile.edu_level)은 **KLIPS 코드**(5=고졸 6=전문대 7=대졸
# 8=석사 9=박사)인데 YP 패널은 1~5 사다리(1=중졸이하 2=고졸 3=전문대 4=대졸 5=대학원)다.
# 변환 없이 그대로 넣으면 대졸(7)이 YP 최대값(5)보다 커서 z-거리가 5σ 가까이 튀고,
# 매칭이 '학력 최상위 응답자' 로 쏠린다 — 만족도 궤적이 통째로 편향됐다.
KLIPS_TO_YP_EDU = {2: 1, 3: 1, 4: 1, 5: 2, 6: 3, 7: 4, 8: 5, 9: 5}


def _yp_edu(edu) -> float | None:
    """KLIPS 학력코드 → YP 학력 사다리. 이미 YP 범위(1~5)면 그대로 둔다."""
    if edu is None:
        return None
    try:
        v = int(round(float(edu)))
    except (TypeError, ValueError):
        return None
    return float(KLIPS_TO_YP_EDU.get(v, min(max(v, 1), 5)))


@lru_cache(maxsize=1)
def _yp_panel():
    """YP 청년패널 — 웨이브별 종합 만족도(1~5) 추적용. (KLIPS 엔 만족도 없음)"""
    if not YP_PATH.exists():
        return None
    y = pd.read_csv(YP_PATH)
    for c in SATIS + YP_FEATS:
        if c in y.columns:
            y[c] = pd.to_numeric(y[c], errors="coerce")
    have = [c for c in SATIS if c in y.columns]
    if not have:
        return None
    y["만족도"] = y[have].mean(axis=1)
    y = y.sort_values(["person_id", "wave"])
    events = _yp_events(y)
    y = y.dropna(subset=["age", "sex", "만족도"])
    match = y.dropna(subset=YP_FEATS)
    if len(match) < 50:
        return None
    mu, sd = match[YP_FEATS].mean(), match[YP_FEATS].std().replace(0, 1)
    # 예전엔 {person_id: DataFrame} 사전(12,000여 개 객체)을 만들어 두고 시작점마다
    # `.loc[wave]` 로 한 행씩 꺼냈다. 시작점 300 × 연차 4 × facet 5 = 6,000회 파이썬
    # 루프 + pandas 스칼라 인덱싱이 되면서 /compare 시간의 절반 이상을 잡아먹었고,
    # 사전 자체가 서버 첫 기동을 수 초 늦췄다. → long 프레임 하나만 두고 merge 로
    # 한 번에 따라간다(project_trajectory 가 이미 쓰던 방식).
    keep = ["person_id", "wave", "만족도"] + [c for c in SATIS if c in y.columns]
    long = y[keep].drop_duplicates(subset=["person_id", "wave"])
    return {"match": match, "mu": mu, "sd": sd, "long": long, "events": events}


def _yp_events(y: pd.DataFrame) -> dict:
    """{treatment: {person_id: [이벤트가 일어난 wave, ...]}}.

    없는 컬럼은 조용히 건너뛴다(해당 선택은 분기 불가 → 기준 궤적으로 폴백).
    """
    ev: dict[str, dict] = {}
    if "changed_job" in y.columns:
        mv = y[pd.to_numeric(y["changed_job"], errors="coerce") == 1]
        ev["move"] = mv.groupby("person_id")["wave"].apply(list).to_dict()
    if "income_self" in y.columns:
        se = y[pd.to_numeric(y["income_self"], errors="coerce").notna()]
        ev["startup"] = se.groupby("person_id")["wave"].apply(list).to_dict()
    if "edu_level" in y.columns:
        prev = y.groupby("person_id")["edu_level"].shift(1)
        up = y[y["edu_level"] > prev]
        ev["enroll"] = up.groupby("person_id")["wave"].apply(list).to_dict()
    return ev


def _filter_starts(ordered, events: dict, treatment: str | None, horizon: int,
                   k: int):
    """유사도 순 시작점 중 '그 선택을 실제로 한 사람'만 남긴다.

    `stay` 는 이직 이벤트가 **없는** 사람 = move 의 여집합.

    가장 가까운 k명만 보면 하위집단이 금방 바닥난다(YP 는 4웨이브뿐이라 시작 웨이브가
    늦으면 관측창에 이벤트가 들어올 자리가 없다). 그래서 **필요한 만큼만** 이웃 반경을
    넓힌다 — 유사도를 표본과 맞바꾼 것이므로 `k_used` 로 얼마나 넓혔는지 남긴다.

    확대는 `MAX_WIDEN` 배까지만. 끝까지 넓히면 나이대만 같은 사람 전체가 돼서
    '너와 비슷한 사람들' 이라는 전제 자체가 사라진다 — 그 지점을 넘느니 분기를
    포기하고 전체 기준 궤적으로 후퇴하는 게 정직하다.
    """
    base = ordered[:k]
    if not treatment or treatment not in YP_EVENTS:
        return base, {"branched": False, "reason": "선택 유형에 해당하는 이벤트 정의 없음"}

    src_key = "move" if treatment == "stay" else treatment
    waves_by_pid = events.get(src_key)
    if waves_by_pid is None:
        return base, {"branched": False,
                      "reason": f"YP 패널에 '{YP_EVENTS[treatment]}' 이벤트 컬럼 없음"}

    want_hit = treatment != "stay"

    def _hit(pid, w0):
        return any(w0 < w <= w0 + horizon for w in waves_by_pid.get(pid, []))

    kept, k_used, limit = [], k, min(k * MAX_WIDEN, len(ordered))
    for k_try in (k, k * 2, limit):
        k_try = min(k_try, limit)
        kept = [s for s in ordered[:k_try] if _hit(*s) is want_hit]
        k_used = k_try
        if len(kept) >= MIN_BRANCH_N:
            break

    meta = {"treatment": treatment, "label": YP_EVENTS[treatment],
            "matched_n": k_used, "k_requested": k, "branch_n": len(kept)}
    if len(kept) < MIN_BRANCH_N:
        meta.update(branched=False,
                    reason=f"유사인 {k_used}명까지 넓혀도 '{YP_EVENTS[treatment]}' 한 "
                           f"사람이 {len(kept)}명(<{MIN_BRANCH_N}) — "
                           "분기 대신 전체 기준 궤적 사용")
        return base, meta
    meta.update(branched=True,
                widened=k_used > k,
                note=("표본 확보를 위해 유사 이웃 범위를 넓힘 — 개인화 정밀도는 그만큼 낮음"
                      if k_used > k else None))
    return kept, meta


@lru_cache(maxsize=16)
def _yp_ordered(age: float, sex: float, wage: float, edu: float,
                min_n: int) -> tuple:
    """프로필 → 유사도 순 (person_id, wave) 전체 목록.

    **프로필만으로 정해지는 값**이라 A/B 가 똑같이 쓴다(선택별로 갈리는 건 뒤의
    이벤트 필터뿐). /compare 는 시나리오를 두 번 그리므로 캐시하지 않으면 같은
    거리 계산·정렬을 두 번 한다. 키는 숫자 4개라 캐시가 가볍다.
    """
    P = _yp_panel()
    match, mu, sd = P["match"], P["mu"], P["sd"]
    cand = match[match["age"].between(age - 1, age + 1)]
    if len(cand) < min_n:
        return ()
    q = {"age": age, "sex": sex, "income_now": wage, "edu_level": edu}
    zq = np.array([(q[c] - mu[c]) / sd[c] for c in YP_FEATS])
    Z = ((cand[YP_FEATS] - mu) / sd).to_numpy()
    dist = np.sqrt(((Z - zq) ** 2).sum(axis=1))
    arr = cand.assign(_d=dist).sort_values("_d")[["person_id", "wave"]].to_numpy()
    return tuple(map(tuple, arr))


def _yp_starts(features: dict, k: int, min_n: int, treatment: str | None,
               horizon: int):
    """프로필과 가장 비슷한 YP 응답자의 (person_id, 시작wave) 목록 + 분기 메타.

    반환 (P, starts, branch) — P 가 None 이면 패널 없음.
    """
    P = _yp_panel()
    if P is None:
        return None, [], {"branched": False, "reason": "YP 패널 없음"}
    match = P["match"]
    A = features.get("age")
    if A is None:
        return P, [], {"branched": False, "reason": "나이 미입력"}
    try:
        sex = float(features.get("sex"))
    except (TypeError, ValueError):
        sex = float(match["sex"].median())
    W = features.get("monthly_wage")
    if W is None:
        near = match[match["age"].between(A - 1, A + 1)]["income_now"]
        W = float(near.median()) if len(near) else float(match["income_now"].median())
    edu = _yp_edu(features.get("edu_level"))
    if edu is None:
        edu = float(match["edu_level"].median())

    ordered = _yp_ordered(float(A), sex, float(W), edu, min_n)
    if not ordered:
        return P, [], {"branched": False, "reason": "유사 표본 부족(청년 범위 밖)"}
    starts, branch = _filter_starts(ordered, P["events"], treatment, horizon, k)
    return P, starts, branch


def _follow(starts, P: dict, horizon: int) -> pd.DataFrame:
    """시작점 목록 → 각 시작점의 t+0..t+horizon 관측을 붙인 long 프레임.

    시작점마다 `.loc` 로 한 행씩 꺼내는 대신 merge 한 번으로 전부 따라간다.
    같은 사람이 여러 시작 웨이브로 뽑혔으면 각각을 별개 시작점으로 센다
    (기존 루프 동작과 동일).
    """
    s = pd.DataFrame(list(starts), columns=["person_id", "start_wave"])
    f = s.merge(P["long"], on="person_id", how="left")
    f["h"] = f["wave"] - f["start_wave"]
    return f[f["h"].between(0, horizon)]


def yp_satisfaction(features: dict, horizon: int = 3, k: int = 300,
                    min_n: int = 15, treatment: str | None = None) -> dict:
    """만족도 궤적 + facet별 궤적 + 분기 메타를 **한 번의 추적으로** 산출.

    예전엔 종합 만족도와 facet 을 각각 계산하면서 매칭도 두 번, 추적도 두 번 했다.
    둘은 같은 하위집단을 봐야 하므로 나눠 돌 이유가 없었다.

    반환 {points, facets, branch}
      · points  = [{year, age, sample_n, satis_p25/p50/p75}]  종합 만족도(1~5)
      · facets  = {facet_key: [{year, age, sample_n, mean}]}  세부 5개
                  (facet 은 1~5 정수라 중앙값이 4로 뭉개져 → 평균값 사용)
      · branch  = 선택별 분기가 적용됐는지 + 안 됐으면 사유
    """
    P, starts, branch = _yp_starts(features, k, min_n, treatment, horizon)
    empty = {"points": [], "facets": {}, "branch": branch}
    if P is None or not len(starts):
        return empty
    A = features.get("age")
    f = _follow(starts, P, horizon)
    if f.empty:
        return empty
    base_age = int(A)

    # ── 종합 만족도: 연차별 분위수 ─────────────────────────────────────────
    g = f.dropna(subset=["만족도"]).groupby("h")["만족도"]
    n = g.size()
    q = g.quantile([0.25, 0.5, 0.75]).unstack() if len(n) else pd.DataFrame()
    points = [
        {"year": int(h), "age": base_age + int(h), "sample_n": int(n[h]),
         "satis_p25": round(float(q.loc[h, 0.25]), 2),
         "satis_p50": round(float(q.loc[h, 0.50]), 2),
         "satis_p75": round(float(q.loc[h, 0.75]), 2)}
        for h in sorted(n.index) if n[h] >= min_n
    ]

    # ── facet: 연차별 평균 + 유효 관측 수 ─────────────────────────────────
    cols = [c for c in SATIS if c in f.columns]
    facets: dict = {}
    if cols:
        agg = f.groupby("h")[cols].agg(["mean", "count"])
        for c in cols:
            series = [
                {"year": int(h), "age": base_age + int(h),
                 "sample_n": int(agg.loc[h, (c, "count")]),
                 "mean": round(float(agg.loc[h, (c, "mean")]), 2)}
                for h in sorted(agg.index)
                if agg.loc[h, (c, "count")] >= min_n
            ]
            if series:
                facets[c] = series
    return {"points": points, "facets": facets, "branch": branch}


def wellbeing_branch(features: dict, horizon: int = 3, k: int = 300,
                     min_n: int = 15, treatment: str | None = None) -> dict:
    """만족도 궤적 + 분기 메타 {points, branch}. (facet 까지 필요하면 yp_satisfaction)"""
    r = yp_satisfaction(features, horizon, k, min_n, treatment)
    return {"points": r["points"], "branch": r["branch"]}


def project_wellbeing_trajectory(features: dict, horizon: int = 3, k: int = 300,
                                 min_n: int = 15,
                                 treatment: str | None = None) -> list[dict]:
    """프로필 → 향후 몇 년 '종합 만족도(1~5)' 궤적 (청년·YP 4웨이브 기준).

    소득 궤적과 짝지어 "돈은 늘지만 만족도는?"에 답한다. 청년 범위 밖이면 빈 리스트.
    """
    return yp_satisfaction(features, horizon, k, min_n, treatment)["points"]


def project_satisfaction_facets(features: dict, horizon: int = 3, k: int = 300,
                                min_n: int = 15,
                                treatment: str | None = None) -> dict:
    """프로필 → 만족도 세부 facet별 궤적(직무·자기발전·소득·고용안정·장래성).

    `treatment` 를 주면 종합 만족도와 **같은 하위집단**으로 facet 도 분기한다
    → "이직한 사람들은 소득 만족은 올랐는데 고용안정 만족은 떨어지더라" 가 가능해진다.
    """
    return yp_satisfaction(features, horizon, k, min_n, treatment)["facets"]
