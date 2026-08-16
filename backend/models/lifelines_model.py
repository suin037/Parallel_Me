"""lifelines: 상태 지속기간 생존분석 (L4 — '후회 리스크' 타임라인).

v4: **treatment 축을 추가**했다.
    · move    (이직) — 재직 스펠. 청년 lifelines_yp.pkl / 그 외 lifelines_klips.pkl
                       / 폴백 lifelines.pkl(GOMS; encoders 별도)
    · startup (창업) — lifelines_klips_startup.pkl. **자영 상태 스펠**의 이탈위험.
                       기존엔 KOSIS 기업생멸(집단통계)로만 답하던 자리를 개인단위
                       모델로 바꾼다. 단 이벤트는 '사업체 폐업' 이 아니라 '응답자가
                       자영 상태에서 벗어남'(폐업·업종전환·재취업 포함)이다.
    · break   (쉬어가기) — lifelines_klips_break.pkl. **일자리 사이 공백 스펠**.
                       이벤트는 '다음 일자리 시작(복귀)' 이므로 지속기간은
                       '얼마나 쉬게 되는가' 다. 다른 treatment 는 상태가 **끝나는**
                       위험을 재는데, 여기서만 상태가 끝나는 게 곧 **복귀**다.
                       파동이 아니라 직업력의 월 단위 시점으로 만들어 length bias 가 없다.
    · enroll  (진학) — 없음(이탈을 정의할 스펠 자체가 없다).
"""

from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from config import settings

YOUTH_MAX = 31

TREATMENT_FILES: dict[str, dict[str, str]] = {
    "move": {"yp": "lifelines_yp.pkl", "klips": "lifelines_klips.pkl",
             "goms": "lifelines.pkl"},
    "startup": {"klips": "lifelines_klips_startup.pkl"},
    "break": {"klips": "lifelines_klips_break.pkl"},
}


@lru_cache(maxsize=1)
def _load_all() -> dict:
    """{treatment: {source: (art, enc)}}."""
    A = settings.artifacts_abspath
    out: dict[str, dict] = {}
    for treatment, files in TREATMENT_FILES.items():
        found: dict[str, tuple] = {}
        for key, fname in files.items():
            p = A / fname
            if not p.exists():
                continue
            art = joblib.load(p)
            enc = joblib.load(A / "encoders.pkl") if key == "goms" else art
            found[key] = (art, enc)
        if found:
            out[treatment] = found
    return out


def available_treatments() -> list[str]:
    """개인단위 생존(L4)을 제공할 수 있는 treatment 목록."""
    return sorted(_load_all())


def _select(features: dict, treatment: str = "move") -> tuple:
    arts = _load_all().get(treatment)
    if not arts:
        raise RuntimeError(f"'{treatment}' lifelines artifact 가 없습니다.")
    age = features.get("age")
    youth = age is not None and float(age) <= YOUTH_MAX
    order = ("yp", "klips", "goms") if youth else ("klips", "yp", "goms")
    for key in order:
        if key in arts:
            return arts[key]
    return next(iter(arts.values()))


def _industry_row(features: dict, art: dict) -> dict[str, float]:
    """업종(KSIC 대분류 문자) → Cox 더미 값.

    창업 모델에만 있는 축이다. `features["ksic_section"]` 은 자유입력에서 뽑는다
    (`choice_classifier.extract_startup_context`).

    업종을 모를 때 0 으로 채우면 **기준 업종(도소매)의 위험을 그대로 뒤집어쓴다.**
    그건 '모름' 이 아니라 특정 업종을 찍는 것이므로, 학습 표본의 업종 구성 평균
    (`industry_means`)으로 채워 '평균적인 창업' 에 해당하는 위험을 낸다.
    """
    cols = art.get("industry_cols") or []
    if not cols:
        return {}
    means = art.get("industry_means", {})
    sec = features.get("ksic_section")
    if not sec:
        return {c: float(means.get(c, 0.0)) for c in cols}
    if sec == art.get("industry_reference"):
        return {c: 0.0 for c in cols}          # 기준 범주 = 더미 전부 0
    target = f"ind_{sec}"
    if target not in cols:
        # 학습 때 표본이 얇아 '기타' 로 합쳐진 업종
        target = "ind_기타"
        if target not in cols:
            return {c: float(means.get(c, 0.0)) for c in cols}
    return {c: (1.0 if c == target else 0.0) for c in cols}


def _covariate_frame(features: dict, art: dict, enc: dict) -> pd.DataFrame:
    ind = _industry_row(features, art)
    row = [ind[c] if c in ind else _value(c, features, enc) for c in art["cov_cols"]]
    return pd.DataFrame([row], columns=art["cov_cols"])


def _value(col: str, features: dict, enc: dict) -> float:
    med = enc.get("medians", {})
    if col in ("age", "age_start"):
        return float(features.get("age", med.get(col, 30)))
    if col == "sex":
        try:
            return float(features.get("sex"))
        except (TypeError, ValueError):
            return med.get(col, 1)
    if col == "sex_enc":
        return enc["sex_map"].get(str(features.get("sex")), 0)
    if col == "major_enc":
        return enc["major_map"].get(str(features.get("major")), 0)
    v = features.get(col)
    return med.get(col, 0) if v is None else float(v)


def estimate_survival(features: dict, treatment: str = "move") -> float:
    """예상 상태 지속기간 중앙값(개월). 이직=재직기간, 창업=자영 유지기간."""
    art, enc = _select(features, treatment)
    X = _covariate_frame(features, art, enc)
    med = art["cox"].predict_median(X)
    v = float(med.iloc[0]) if hasattr(med, "iloc") else float(med)
    if not np.isfinite(v):
        v = float(art["km"].median_survival_time_)
    return v


def model_confidence(features: dict, treatment: str = "move") -> dict | None:
    """이 입력에 쓰인 L4 생존모델의 신뢰지표(5-fold C-index 등). 없으면 None.

    학습 시 저장된 `cv_concordance`(train/test/gap)와 표본수·관측범위를 그대로 노출한다.
    ('정직한 불확실성' 차별점 — UI/응답에 예측력 지표를 함께 보여주기 위함)
    """
    try:
        art, _ = _select(features, treatment)
    except RuntimeError:
        return None
    cv = art.get("cv_concordance")
    if not cv:
        return None
    out = {
        "metric": "5-fold C-index",
        "c_index_test": cv.get("test"),
        "c_index_train": cv.get("train"),
        "overfit_gap": cv.get("gap"),
        "n_spells": art.get("n"),
        "treatment": treatment,
        "event_label": art.get("event_label", "일자리 이탈(이직)"),
        "source": art.get("source"),
        "max_horizon_years": art.get("max_horizon_years"),
    }
    if art.get("industry_used"):
        # 업종축이 켜졌는지, 이 요청의 업종이 실제로 잡혔는지를 응답에 남긴다.
        sec = features.get("ksic_section")
        out["industry_axis"] = {
            "enabled": True,
            "applied_section": sec,
            "resolved": bool(sec),
            "reference": art.get("industry_reference"),
            "cv_gain": art.get("industry_cv_gain"),
            "note": ("업종별 이탈위험 적용" if sec else
                     "업종 미상 — 학습표본 업종 구성 평균으로 대체"),
        }
    return out


def return_timeline(features: dict, months=(3, 6, 12, 24),
                    treatment: str = "break") -> dict[int, float]:
    """{개월: 복귀 누적확률} — 'break' 전용.

    `risk_timeline` 과 계산은 같지만 **의미가 반대**다. 다른 treatment 의 이벤트는
    상태 이탈(이직·폐업)이라 나쁜 쪽이지만, 여기서 이벤트는 다음 일자리 시작
    = 복귀다. 그래서 같은 곡선을 '후회 리스크' 로 부르면 안 되고, 단위도 연이
    아니라 개월이다(쉬는 기간 중앙값이 1년 미만이라 연 단위로는 다 뭉개진다).
    """
    art, enc = _select(features, treatment)
    X = _covariate_frame(features, art, enc)
    sf = art["cox"].predict_survival_function(X)
    idx = np.asarray(sf.index, dtype=float)
    max_months = art.get("max_horizon_years", 5) * 12
    out = {}
    for mo in months:
        if mo > max_months:
            continue
        out[mo] = round(1 - float(sf.iloc[int(np.abs(idx - mo).argmin()), 0]), 3)
    return out


def risk_timeline(features: dict, years=(1, 3, 5, 10),
                  treatment: str = "move") -> dict[int, float]:
    """N년 후 이탈 누적확률 - 서비스 '후회 리스크' 멘트용.

    이직=일자리 이탈, 창업=자영 상태 이탈. 관측 범위(모델 스펠 최대 기간)를 크게
    벗어나는 연차는 과대추정 방지를 위해 스킵.
    → KLIPS(≈10년)는 10년까지, YP(≈4년)는 관측 내 연차만.
    """
    art, enc = _select(features, treatment)
    X = _covariate_frame(features, art, enc)
    sf = art["cox"].predict_survival_function(X)
    idx = np.asarray(sf.index, dtype=float)
    max_yr = art.get("max_horizon_years", 10)   # 소스별 신뢰 최대 연차(KLIPS10/YP5)
    out = {}
    for yr in years:
        if yr > max_yr:            # 신뢰 범위 밖 → 스킵(과대추정 방지)
            continue
        m = yr * 12
        out[yr] = round(1 - float(sf.iloc[int(np.abs(idx - m).argmin()), 0]), 3)
    return out
