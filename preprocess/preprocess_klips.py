"""KLIPS 원본(.sav) → 종단 패널 + 직장 스펠. (L3/L4 학습 · L5 궤적의 입력)

`klips_train.py` 와 `backend/trajectory.py` 가 요구하는 두 파일을 만든다.

    data/raw/klips/klips_base.pkl        개인-연도 패널
    data/raw/klips/klips_base_생존.csv    직장 스펠(생존분석용)
    data/raw/klips/klips_build_report.json 빌드 메타(차수·연도·CPI·표본수)

## 왜 다시 만드는가
이전 빌드는 **1~10차(1998~2007)** 였고 `월임금_실질` 컬럼이 **이름만 실질인 명목값**이었다.
그 결과 서비스가 보여주는 소득 궤적이 20년 전 임금 수준이었고, 성장률(%)에는
물가상승분이 성장으로 섞여 들어갔다. 이 스크립트는

  1. **12~27차(2009~2024)** 로 재빌드하고,
  2. 명목 월임금을 CPI 로 **실제 디플레이트**해 `월임금_실질`(기준연도 표기)로 만든다.

## 차수 ↔ 연도
KLIPS 는 1차=1998 이므로 `연도 = 차수 + 1997` (18차=2015 … 27차=2024).

## 원본 변수 (차수 w 는 2자리, 예: 18)
| 컬럼 | 변수 | 비고 |
|---|---|---|
| pid | `pid` | 개인고유번호 |
| 성별 | `p{w}0101` | 1=남 2=여 (GOMS/YP 와 동일 코딩) |
| 나이 | `p{w}0107` | 만나이 |
| 학력 | `p{w}0110` | 2=무학 … 5=고졸 6=전문대 7=대졸 8=석사 9=박사 |
| 직종 | `p{w}0352` | 표준직업분류 7차(2017코드) |
| 산업 | `p{w}0342` | 표준산업분류 **10차**(2017코드). 12차부터 존재 |
| 종업원규모 | `p{w}0403` | 전체종업원수(범주). 없으면 `p{w}0402`(명) 를 범주화 |
| 종사상지위 | `p{w}0314` | 1=상용 2=임시 3=일용 4=자영 5=무급가족 |
| 월임금_명목 | `p{w}1642` | **임금근로자** 월평균임금(만원) |
| 자영소득_명목 | `p{w}1672` | **비임금근로자**(자영) 월평균소득(만원) |
| 취업년/월 | `p{w}0301` / `p{w}0302` | 현 일자리 시작시점 → 근속·이직 파생 |
| 직무만족 | `p{w}4321` | 전반적 일자리 만족도(단일항목). **취업자만 응답** |
| 생활만족 | `p{w}6508` | 전반적 생활만족도. 전체 응답자 |
| 건강 | `p{w}6101` | 현재 건강상태(주관적). 전체 응답자 |
| 근무환경만족 | `p{w}4314` | 요인별 직무만족-근무환경. 취업자만 |
| 근로시간만족 | `p{w}4315` | 요인별 직무만족-근로시간. 취업자만 |
| 가족관계만족 | `p{w}6504` | 생활만족 배터리. 전체 응답자 |
| 친인척관계만족 | `p{w}6505` | 생활만족 배터리. 전체 응답자 |
| 사회관계만족 | `p{w}6506` | 사회적 친분관계. 전체 응답자 |

## 결과변수를 소득 하나만 두지 않는 이유
L3/L4 의 Y 는 오랫동안 `월소득_실질` 하나였다. 그런데 이직의 인과효과는 소득에서는
**≈0(비유의)** 이라, 그 선택으로 무엇이 달라지는지를 데이터가 말해주지 못했다. 위
5개 문항은 12~27차 전 차수에 같은 코드로 있으므로, 처치·혼재변수 정의를 그대로 두고
Y 만 갈아끼우면 같은 인과 틀에서 만족·건강 효과를 잴 수 있다.

## ⚠ 5점 척도 방향 (역코딩)
`.sav` 에 값 라벨이 비어 있어 코드북 없이는 방향을 읽을 수 없다. 그래서 **데이터로**
확인했다(27차): `corr(임금, 직무만족코드) = -0.25`, `corr(나이, 건강코드) = +0.47`.
즉 원본은 **1 = 가장 좋음 … 5 = 가장 나쁨** 이다. 그대로 쓰면 "이직하면 만족도가
내려간다" 처럼 **모든 효과의 부호가 뒤집힌다.** → `6 - x` 로 뒤집어 저장하며, 이
파일이 내보내는 5개 컬럼은 전부 **값이 클수록 좋음**이다.

`p{w}1642` 는 임금근로자만 응답한다 → 자영(종사상지위 4) 행은 임금이 100% 결측이다.
그래서 창업(임금근로→자영) 전이의 **결과변수가 통째로 관측되지 않았다**. 비임금근로자
소득 `p{w}1672` 를 함께 읽어 `월소득_*`(둘을 합친 총소득)을 만든다. 임금만 보는
기존 컬럼(`월임금_*`)은 하위호환을 위해 그대로 둔다(L5 궤적·이직 L3 이 쓴다).

KLIPS 는 무응답을 `-1` 로 코딩한다 → 전부 결측 처리한다.

## 파생
- `근속기간` (년) = 조사연도 − 취업년, 0 미만은 0 으로 절단
- `이직` (0/1) = 직전 관측 차수 대비 **일자리 시작시점(년,월) 이 바뀌었으면 1**.
  직전에 일자리가 없었으면(신규취업) 이직으로 세지 않는다.
- 스펠 = (pid, 일자리 시작시점) 묶음. `duration` 은 그 일자리의 **최종 관측 근속연수**,
  `event` 는 그 뒤에도 관측이 있으면 1(종료 확인), 마지막 관측이면 0(중도절단).

사용법:
    python preprocess/preprocess_klips.py
    python preprocess/preprocess_klips.py --waves 12-27 --base-year 2024
    python preprocess/preprocess_klips.py --klips-dir "../KLIPS" --out data/raw/klips
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

WAVE_YEAR_OFFSET = 1997          # 1차 = 1998
DEFAULT_KLIPS_DIR = Path("../KLIPS")
DEFAULT_OUT = Path("data/raw/klips")
CPI_PATH = Path("data/reference/cpi_korea_2020base.csv")

# 종업원수(명) → 범주 코드. p{w}0403 범주와 결이 같도록 계단식으로 자른다.
FIRM_SIZE_BINS = [0, 4, 9, 29, 49, 99, 299, 499, 999, np.inf]

# ── 만족·건강 5점 척도 (소득 외 결과변수) ─────────────────────────────────────
# 표준명 → 항목코드. 차수 접두사 p{w} 만 바뀌고 코드는 12~27차 내내 동일하다.
# 전부 원본이 1=가장 좋음 … 5=가장 나쁨 이라 `6 - x` 로 뒤집어 **클수록 좋음**으로
# 통일한다(위 docstring "⚠ 5점 척도 방향" 참고).
LIKERT5 = {
    "직무만족": "4321",       # 전반적 일자리 만족도 — 취업자만 응답
    "생활만족": "6508",       # 전반적 생활만족도 — 전체
    "건강": "6101",           # 현재 건강상태(주관적) — 전체
    "근무환경만족": "4314",   # 요인별 직무만족 - 근무환경
    "근로시간만족": "4315",   # 요인별 직무만족 - 근로시간
    # 생활만족 배터리의 관계 3종. 6508(전반)과 같은 문항군이라 방향·무응답 처리가 같다.
    # 코드는 추정이 아니라 27차 원본 p276504~6506 을 klips_health.csv 의 기존 값과
    # pid 로 대조해 확정했다(23,164명 전원 100% 일치).
    "가족관계만족": "6504",   # 가족관계 만족도 — 전체
    "친인척관계만족": "6505",  # 친인척관계 만족도 — 전체
    "사회관계만족": "6506",   # 사회적 친분관계 만족도 — 전체
}
LIKERT_MIN, LIKERT_MAX = 1, 5

# ── KSIC 10차 중분류(2자리) → 대분류(A~U) ────────────────────────────────────
# `p{w}0342` 는 표준산업분류 **10차** 소분류 코드다. KOSIS 기업생멸통계의
# `ksic_section` 과 같은 분류 체계라, 대분류로 접으면 두 데이터가 같은 축에서 만난다
# (창업 생존율은 집단통계, 자영 이탈위험은 개인단위 — 같은 업종 기준으로 읽힌다).
#
# ⚠ SPSS 에 숫자로 저장돼 **선행 0 이 날아간다**: 011(작물재배업) 이 11 로 들어온다.
#   3자리로 zero-pad 한 뒤 앞 2자리를 취해야 농림어업(A)이 제조업(C)으로 새지 않는다.
KSIC10_SECTION_BOUNDS = [
    (1, 3, "A"),    (5, 8, "B"),    (10, 34, "C"),  (35, 35, "D"), (36, 39, "E"),
    (41, 42, "F"),  (45, 47, "G"),  (49, 52, "H"),  (55, 56, "I"), (58, 63, "J"),
    (64, 66, "K"),  (68, 68, "L"),  (70, 73, "M"),  (74, 76, "N"), (84, 84, "O"),
    (85, 85, "P"),  (86, 87, "Q"),  (90, 91, "R"),  (94, 96, "S"), (97, 98, "T"),
    (99, 99, "U"),
]


def ksic_section(code) -> str | None:
    """KSIC 10차 소분류 코드 → 대분류 문자. 분류 밖(공백 구간)이면 None."""
    if pd.isna(code) or code <= 0:
        return None
    major = int(str(int(code)).zfill(3)[:2])
    for lo, hi, sec in KSIC10_SECTION_BOUNDS:
        if lo <= major <= hi:
            return sec
    return None


def parse_waves(spec: str) -> list[int]:
    """'18-27' 또는 '18,19,20' → [18, 19, ...]"""
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-"))
            out.extend(range(lo, hi + 1))
        elif part:
            out.append(int(part))
    return sorted(set(out))


def load_cpi(path: Path) -> dict[int, float]:
    if not path.exists():
        raise FileNotFoundError(
            f"CPI 기준표가 없습니다: {path}\n"
            "data/reference/README.md 참고 — 실질임금 환산 없이는 빌드하지 않는다."
        )
    df = pd.read_csv(path)
    return {int(r["year"]): float(r["cpi"]) for _, r in df.iterrows()}


def _blank_negatives(s: pd.Series) -> pd.Series:
    """KLIPS 무응답 코드(-1 등 음수)와 직종 999(분류불능) 를 결측으로."""
    return s.mask(s < 0)


def read_wave(klips_dir: Path, w: int) -> pd.DataFrame:
    """차수 w 의 개인파일 → 표준 스키마 1개 DataFrame."""
    import pyreadstat

    path = klips_dir / f"klips{w:02d}p.sav"
    if not path.exists():
        raise FileNotFoundError(f"{path} 없음")

    src = {
        "성별": f"p{w}0101",
        "나이": f"p{w}0107",
        "학력": f"p{w}0110",
        "직종": f"p{w}0352",
        "산업": f"p{w}0342",
        "종업원규모_범주": f"p{w}0403",
        "종업원규모_명": f"p{w}0402",
        "종사상지위": f"p{w}0314",
        "월임금_명목": f"p{w}1642",
        "자영소득_명목": f"p{w}1672",
        "취업년": f"p{w}0301",
        "취업월": f"p{w}0302",
        **{name: f"p{w}{code}" for name, code in LIKERT5.items()},
    }
    # 산업(10차 코드)은 12차부터 있다. 그 앞 차수는 8차/9차 코드뿐이라 그냥 비운다
    # — 다른 분류 체계를 억지로 10차에 끼워 맞추면 업종별 수치가 조용히 틀어진다.
    present = set(pyreadstat.read_sav(str(path), metadataonly=True)[1].column_names)
    src = {k: v for k, v in src.items() if v in present}
    raw, _ = pyreadstat.read_sav(str(path), usecols=["pid", *src.values()])

    d = pd.DataFrame({"pid": raw["pid"]})
    for name, col in src.items():
        d[name] = _blank_negatives(pd.to_numeric(raw[col], errors="coerce"))
    for name in ("산업", "직종", *LIKERT5):
        if name not in d.columns:
            d[name] = np.nan

    # 5점 척도: 범위 밖은 결측 처리하고 방향을 뒤집는다(클수록 좋음).
    # 뒤집기 전에 범위를 거르는 이유 — 6 이나 8 같은 미정의 코드가 섞이면 뒤집은 뒤엔
    # 0 이나 음수가 되어 '아주 나쁨' 보다 더 나쁜 값으로 조용히 살아남는다.
    for name in LIKERT5:
        v = d[name].where(d[name].between(LIKERT_MIN, LIKERT_MAX))
        d[name] = (LIKERT_MIN + LIKERT_MAX) - v

    d["직종"] = d["직종"].mask(d["직종"] >= 999)          # 999 = 분류불능
    d["산업대분류"] = d["산업"].map(ksic_section)
    for c in ("월임금_명목", "자영소득_명목"):
        d[c] = d[c].mask(d[c] <= 0)

    # 총소득 = 임금근로자면 임금, 비임금(자영)이면 사업소득. 두 문항은 상호배타적이라
    # 한쪽만 응답한다 → 창업 전이의 결과변수를 이 컬럼으로 관측한다.
    d["월소득_명목"] = d["월임금_명목"].fillna(d["자영소득_명목"])
    d["자영여부"] = (d["종사상지위"] == 4).astype("float64").mask(d["종사상지위"].isna())

    # 종업원규모: 범주 응답 우선, 없으면 인원수 응답을 같은 결의 범주로 환산
    binned = pd.cut(d.pop("종업원규모_명"), bins=FIRM_SIZE_BINS,
                    labels=False, right=True).astype("float64") + 1
    d["종업원규모"] = d.pop("종업원규모_범주").fillna(binned)

    d["wave"] = w
    d["year"] = w + WAVE_YEAR_OFFSET
    return d


def build_panel(klips_dir: Path, waves: list[int], cpi: dict[int, float],
                base_year: int) -> pd.DataFrame:
    frames = []
    for w in waves:
        d = read_wave(klips_dir, w)
        frames.append(d)
        print(f"  [wave {w} / {w + WAVE_YEAR_OFFSET}] {len(d):,}행  "
              f"임금응답 {int(d['월임금_명목'].notna().sum()):,}")
    b = pd.concat(frames, ignore_index=True)

    # ── 실질임금 환산 (기준연도 base_year) ────────────────────────────────
    missing = sorted({int(y) for y in b["year"].unique()} - cpi.keys())
    if missing or base_year not in cpi:
        raise KeyError(
            f"CPI 기준표에 없는 연도: {missing or ''} {'' if base_year in cpi else base_year}\n"
            f"{CPI_PATH} 에 해당 연도를 추가할 것(추정치로 대체하지 않는다)."
        )
    factor = b["year"].map(lambda y: cpi[base_year] / cpi[int(y)])
    b["월임금_실질"] = (b["월임금_명목"] * factor).round(1)
    b["자영소득_실질"] = (b["자영소득_명목"] * factor).round(1)
    b["월소득_실질"] = (b["월소득_명목"] * factor).round(1)

    # ── 근속기간(년) ──────────────────────────────────────────────────────
    b["근속기간"] = (b["year"] - b["취업년"]).clip(lower=0)

    # ── 이직: 직전 관측 대비 일자리 시작시점 변화 ──────────────────────────
    b = b.sort_values(["pid", "wave"]).reset_index(drop=True)
    # 시작시점을 하나의 키로 (월 결측은 0 으로 채워 년만으로도 비교되게)
    b["_job_key"] = np.where(
        b["취업년"].notna(),
        b["취업년"].fillna(0) * 100 + b["취업월"].fillna(0),
        np.nan,
    )
    g = b.groupby("pid", sort=False)
    prev_key, prev_wave = g["_job_key"].shift(1), g["wave"].shift(1)
    b["이직"] = (
        prev_key.notna() & b["_job_key"].notna() & (b["_job_key"] != prev_key)
        & prev_wave.notna()
    ).astype(int)

    cols = ["pid", "wave", "year", "성별", "나이", "학력", "직종",
            "산업", "산업대분류", "종업원규모",
            "종사상지위", "자영여부",
            "월임금_명목", "월임금_실질", "자영소득_실질", "월소득_명목", "월소득_실질",
            *LIKERT5,
            "근속기간", "이직"]
    return b[cols + ["_job_key"]]


def build_spells(b: pd.DataFrame) -> pd.DataFrame:
    """(pid, 일자리 시작시점) → 직장 스펠. duration=최종 관측 근속연수, event=종료확인 여부."""
    emp = b[b["_job_key"].notna()].copy()
    last_obs = b.groupby("pid")["wave"].max().rename("_last_obs_wave")

    sp = (emp.groupby(["pid", "_job_key"], sort=False)
             .agg(시작wave=("wave", "min"), _end_wave=("wave", "max"),
                  duration=("근속기간", "max"))
             .reset_index()
             .merge(last_obs, on="pid", how="left"))

    # 그 일자리의 마지막 관측 뒤에도 이 사람의 관측이 있으면 → 일자리가 끝난 걸 봤다(event=1)
    sp["event"] = (sp["_end_wave"] < sp["_last_obs_wave"]).astype(int)
    sp["duration"] = sp["duration"].clip(lower=0.5)
    sp = sp.sort_values(["pid", "시작wave", "_job_key"])
    sp["jobseq"] = sp.groupby("pid").cumcount() + 1
    # 좌측절단 보정용(현 klips_train 은 미사용, 향후 lifelines entry 인자에 연결):
    # 패널에서 처음 관측될 때 이미 지난 근속연수
    first_seen = (emp.sort_values("wave").groupby(["pid", "_job_key"])["근속기간"]
                     .first().rename("entry_years").reset_index())
    sp = sp.merge(first_seen, on=["pid", "_job_key"], how="left")
    return sp[["pid", "jobseq", "시작wave", "duration", "event", "entry_years"]]


def treatment_counts(b: pd.DataFrame, age_min: int = 20, age_max: int = 45) -> dict:
    """이직 외 treatment(창업·진학)의 전이 표본 규모. 학습 가능 여부 판단 근거.

    `결과관측` = 전이 다음 해에 소득이 실제로 관측된 건수. 인과추정에 실제로
    쓸 수 있는 건 이 수치이며, 이게 작으면 모델을 만들지 **않는** 판단 근거가 된다.
    """
    d = b.sort_values(["pid", "wave"])
    g = d.groupby("pid", sort=False)
    nxt = g.shift(-1)
    cons = (nxt["wave"] - d["wave"]) == 1
    age_ok = d["나이"].between(age_min, age_max)
    y_next = nxt["월소득_실질"].notna()

    startup = cons & d["종사상지위"].isin([1, 2, 3]) & (nxt["종사상지위"] == 4)
    enroll = cons & (nxt["학력"] > d["학력"])          # 학력코드 상승 = 진학(수료)
    grad = enroll & (d["학력"] >= 6)                   # 전문대졸 이상 → 대학원 등

    def _c(m):
        return {"전이": int(m.sum()), "연령내": int((m & age_ok).sum()),
                "연령내_결과관측": int((m & age_ok & y_next).sum())}

    return {"age_band": [age_min, age_max], "창업": _c(startup),
            "진학_전체": _c(enroll), "진학_고등교육이상": _c(grad)}


def main() -> None:
    ap = argparse.ArgumentParser(description="KLIPS 원본 → 종단 패널/스펠")
    ap.add_argument("--klips-dir", type=Path, default=DEFAULT_KLIPS_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--waves", default="12-27",
                    help="예: 12-27 또는 18,19,20. 산업(10차 코드)은 12차부터라 "
                         "그 앞 차수를 넣으면 업종축이 빈다")
    ap.add_argument("--base-year", type=int, default=2024,
                    help="실질임금 기준연도(기본 2024 = 최신 차수)")
    ap.add_argument("--cpi", type=Path, default=CPI_PATH)
    args = ap.parse_args()

    waves = parse_waves(args.waves)
    cpi = load_cpi(args.cpi)
    print(f"[klips] 차수 {waves[0]}~{waves[-1]} "
          f"({waves[0] + WAVE_YEAR_OFFSET}~{waves[-1] + WAVE_YEAR_OFFSET}) "
          f"· 실질임금 기준연도 {args.base_year}")

    b = build_panel(args.klips_dir, waves, cpi, args.base_year)
    sp = build_spells(b)
    b = b.drop(columns=["_job_key"])

    args.out.mkdir(parents=True, exist_ok=True)
    b.to_pickle(args.out / "klips_base.pkl")
    sp.to_csv(args.out / "klips_base_생존.csv", index=False, encoding="utf-8-sig")

    wage = b["월임금_실질"].dropna()
    by_wave = b.groupby("year")["월임금_실질"].median().round(1)
    report = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "waves": waves,
        "years": [waves[0] + WAVE_YEAR_OFFSET, waves[-1] + WAVE_YEAR_OFFSET],
        "deflated": True,
        "cpi_base_year": args.base_year,
        "cpi_source": str(args.cpi),
        "rows": int(len(b)),
        "persons": int(b["pid"].nunique()),
        "wage_rows": int(len(wage)),
        "wage_median_real": float(wage.median()),
        "wage_median_real_by_year": {int(k): float(v) for k, v in by_wave.dropna().items()},
        "job_change_rate": float(b["이직"].mean()),
        "spells": int(len(sp)),
        "spell_events": int(sp["event"].sum()),
        "income_rows_total": int(b["월소득_실질"].notna().sum()),
        "self_employed_rows": int((b["자영여부"] == 1).sum()),
        # 업종(KSIC 10차 대분류) — L4 자영 생존모델의 공변량 후보. 자영 행에서
        # 얼마나 채워졌는지가 곧 '업종별 이탈위험을 낼 수 있는가' 의 근거다.
        "industry_rows": int(b["산업대분류"].notna().sum()),
        "industry_rows_self_employed": int(
            b.loc[b["자영여부"] == 1, "산업대분류"].notna().sum()),
        "industry_dist_self_employed": {
            k: int(v) for k, v in
            b.loc[b["자영여부"] == 1, "산업대분류"].value_counts().items()},
        # 이직 외 treatment 표본 — 창업/진학 모델을 만들 수 있는지의 근거
        "treatment_transitions": treatment_counts(b),
        # 소득 외 결과변수(만족·건강) 관측량. 저장된 값은 역코딩 후 = 클수록 좋음.
        # 취업자만 응답하는 문항(직무만족·근무환경·근로시간)은 행 수가 절반쯤이 정상이다.
        "likert_outcomes": {
            name: {
                "code": code,
                "rows": int(b[name].notna().sum()),
                "mean_reversed": round(float(b[name].mean()), 3),
                "reversed": True,
                "higher_is_better": True,
            }
            for name, code in LIKERT5.items()
        },
    }
    (args.out / "klips_build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[done] 패널 {len(b):,}행 / {b['pid'].nunique():,}명 · 스펠 {len(sp):,}개")
    print(f"       실질임금(기준 {args.base_year}년) 중앙값 {wage.median():.0f}만원 · "
          f"이직률 {b['이직'].mean():.1%}")
    print(f"       연도별 실질임금 중앙값: {by_wave.dropna().to_dict()}")
    tc = report["treatment_transitions"]
    print(f"       treatment 전이(20~45세, 결과관측): "
          f"창업 {tc['창업']['연령내_결과관측']:,} · "
          f"진학 {tc['진학_전체']['연령내_결과관측']:,} "
          f"(고등교육이상 {tc['진학_고등교육이상']['연령내_결과관측']:,})")
    print(f"       → {args.out}/klips_base.pkl, klips_base_생존.csv, klips_build_report.json")


if __name__ == "__main__":
    main()
