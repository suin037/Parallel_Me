"""
preprocess_yp.py  —  YP2021 (청년패널) → data/clean/
=====================================================================
[산출물 2개]
  1) yp_clean.csv   : 사람×웨이브 long 패널  → L2 매칭 · L3 인과추론
  2) yp_spells.csv  : 일자리 spell (duration/event) → L4 생존분석

[GOMS와 다른 점 — 이 3가지가 이 스크립트의 핵심]
  (1) wide → long 변환
      YP는 한 행에 w01~w04가 모두 들어있는 wide 구조.
      L3/L4는 사람×연도 long이 필요 → melt 필요.
  (2) 소득 환산
      소득이 [급여단위(시급/일급/주급/월급) + 금액] 2변수 구조.
      → 월평균(만원)으로 통일 필요. GOMS엔 없던 작업.
  (3) spell 생성
      현직장 시작(y**c101a/b) + 그만둔 시기(y**b136a/b)
      → lifelines가 먹는 (duration_months, event) 형태로 변환.
      ★GOMS로는 불가능했던 L4가 YP로 가능해지는 지점.

실행:  python preprocess_yp.py
필요:  pip install pandas numpy python-calamine
        (YP 엑셀은 비표준 속성 때문에 openpyxl로는 못 읽음 → calamine 사용)
"""

from pathlib import Path
import numpy as np
import pandas as pd

RAW_DIR = Path("data/raw/yp")           # YP2021_w01.xlsx ~ w04.xlsx
OUT_PANEL = Path("data/clean/yp_clean.csv")
OUT_SPELL = Path("data/clean/yp_spells.csv")
CPI_PATH = Path("data/reference/cpi_korea_2020base.csv")
CPI_BASE_YEAR = 2024                    # 실질소득 기준연도(= 최신 웨이브)

WAVES = [1, 2, 3, 4]
WAVE_YEAR = {1: 2021, 2: 2022, 3: 2023, 4: 2024}   # 조사연도(확인 필요)

# ---------------------------------------------------------------------------
# 웨이브 불변 변수 (한 번만 존재)
# ---------------------------------------------------------------------------
ID_VARS = {
    "sampid":  "person_id",     # ★패널 추적 키
    "gender":  "sex",           # 1=남 2=여 (검증 대상)
    "BIRTHy":  "birth_year",
}

# ---------------------------------------------------------------------------
# 웨이브별 변수: {표준변수명: 원변수 템플릿}
#   {w}  = 웨이브 2자리 (01,02,03,04)  → w04age
#   {y}  = y + 웨이브 2자리            → y04c168a
# ---------------------------------------------------------------------------
WAVE_VARS = {
    # --- 인구통계 (w-prefix 계열) ---
    "age":            "w{w}age",
    "edu_level":      "w{w}edu",        # ★GOMS와 달리 학력 변산 있음
    "econ_status":    "w{w}ecoact",     # 경제활동상태(취업/실업/비경활)

    # --- 현재 일자리 (C섹션) ---
    "job_start_y":    "{y}c101a",       # ★spell 시작 (년)
    "job_start_m":    "{y}c101b",       # ★spell 시작 (월)
    "industry_raw":   "{y}c104z",
    "occupation_raw": "{y}b106z",       # 현 직장 주 업무
    "firm_size":      "{y}c109",
    "emp_status":     "{y}c111",        # 종사상 지위(상용/임시/일용)
    "income_unit":    "{y}c168a",       # ★급여단위 1=연봉 2=월평균 3=주당 4=일당 5=시간당
    "income_amount":  "{y}c168b",       # ★금액
    "income_self":    "{y}c224",        # 비임금근로자 소득
    "work_hours":     "{y}c123",        # 주당 근로시간(환산용)
    "work_days":      "{y}c124",        # 주당 근로일수(환산용)

    # --- 만족도 (1~5, ↑좋을수록) ---
    "satis_work":      "{y}c229",
    "satis_growth":    "{y}c231",   # 자기발전  ★성장지표
    "satis_income":    "{y}c232",
    "satis_stability": "{y}c233",   # 고용안정  ★경제지표
    "satis_future":    "{y}c236",   # 장래성    ★성장지표

    # --- ★그만둔 일자리 (B섹션) = 이직 이벤트 ---
    "job_end_y":       "{y}b136a",  # ★이직 발생 시각 (년)
    "job_end_m":       "{y}b136b",  # ★이직 발생 시각 (월)
    "quit_reason":     "{y}b137",
    "prev_satis":      "{y}b138",
    "prev_income_unit":   "{y}b125a",
    "prev_income_amount": "{y}b125b",
    "prev_emp_type":      "{y}b116",
}

MISSING = [-1, -8, -9, 99, 999, 9999]
WEEKS_PER_MONTH = 4.345
INCOME_MIN, INCOME_MAX = 30, 3000     # 만원/월


# ---------------------------------------------------------------------------
def load_wave(w: int) -> pd.DataFrame:
    """한 웨이브 파일에서 필요 변수만 뽑아 표준변수명으로 rename."""
    path = RAW_DIR / f"YP2021_w{w:02d}.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"없음: {path}")

    print(f"  [w{w:02d}] 로딩...", end=" ", flush=True)
    # engine="calamine": YP 엑셀에 든 비표준 속성(synchVertical) 때문에
    # 기본 openpyxl 엔진이 터진다. calamine(Rust)은 무시하고 읽고 더 빠름.
    df = pd.read_excel(path, engine="calamine")
    print(f"{df.shape[0]:,}행 × {df.shape[1]:,}열", end=" ")

    ww, yy = f"{w:02d}", f"y{w:02d}"
    rename, missing = {}, []
    for std, tpl in WAVE_VARS.items():
        col = tpl.format(w=ww, y=yy)
        if col in df.columns:
            rename[col] = std
        else:
            missing.append(std)

    keep = [c for c in ID_VARS if c in df.columns] + list(rename)
    out = df[keep].rename(columns={**ID_VARS, **rename})
    out["wave"] = w
    out["year"] = WAVE_YEAR[w]
    if missing:
        print(f"| 누락 {len(missing)}개: {missing[:4]}")
    else:
        print("| 전체 매칭 OK")
    return out


def verify_codes(df: pd.DataFrame):
    """★값 코딩 실측 검증 — GOMS의 '2075800' 함정 방지."""
    print("\n" + "=" * 64)
    print("  ★ 값 코딩 검증 (설문지 코딩 == 실제 저장값?)")
    print("=" * 64)
    checks = {
        "sex":         "설문지: 1=남 2=여",
        "income_unit": "설문지: 1=시급 2=일급 3=주급 4=월급",
        "emp_status":  "설문지: 1=상용 2=임시 3=일용...",
        "econ_status": "취업/실업/비경활",
        "satis_work":  "설문지: 1~5 (↑만족)",
        "edu_level":   "학력 코드",
    }
    for col, note in checks.items():
        if col not in df:
            continue
        vc = df[col].value_counts(dropna=False).head(8).sort_index()
        print(f"\n  {col:14s} ({note})")
        print("    " + " | ".join(f"{v}:{n:,}" for v, n in vc.items()))
    print("\n  ▲ 위 값이 설문지 코딩과 다르면 WAVE_VARS/리코딩 수정 필요\n")


def to_monthly_income(amount, unit, hours, days):
    """급여단위별 → 월평균(만원) 환산.

    ★설문지 실제 코딩(p114 문27 / p90 문9):
        1=연봉  2=월평균  3=주당  4=일당  5=시간당
      (이전 버전은 1=시급…4=월급으로 잘못 가정 → 중앙값 73만원 오류)
      금액은 모두 '만원' 단위로 기입됨.
    """
    amount = pd.to_numeric(amount, errors="coerce")
    unit = pd.to_numeric(unit, errors="coerce")
    hours = pd.to_numeric(hours, errors="coerce").fillna(40)   # 주당 근로시간
    days = pd.to_numeric(days, errors="coerce").fillna(5)      # 주당 근로일수

    yearly  = amount / 12                      # 1 연봉  → /12
    monthly = amount                           # 2 월평균 → 그대로
    weekly  = amount * WEEKS_PER_MONTH         # 3 주당
    daily   = amount * days * WEEKS_PER_MONTH  # 4 일당
    hourly  = amount * hours * WEEKS_PER_MONTH # 5 시간당

    out = np.select(
        [unit == 1, unit == 2, unit == 3, unit == 4, unit == 5],
        [yearly, monthly, weekly, daily, hourly],
        default=np.nan,
    )
    return pd.Series(out, index=amount.index)


def load_cpi() -> dict:
    """소비자물가지수(2020=100) 연도별. 필요한 연도가 없으면 중단(추정치 금지)."""
    if not CPI_PATH.exists():
        raise FileNotFoundError(f"CPI 기준표 없음: {CPI_PATH} (data/reference/README.md 참고)")
    cpi = {int(r["year"]): float(r["cpi"])
           for _, r in pd.read_csv(CPI_PATH).iterrows()}
    need = set(WAVE_YEAR.values()) | {CPI_BASE_YEAR}
    if missing := sorted(need - cpi.keys()):
        raise KeyError(f"CPI 기준표에 없는 연도: {missing} → {CPI_PATH} 에 추가할 것")
    return cpi


def build_panel() -> pd.DataFrame:
    print("[1] 웨이브 로딩 + wide→long 변환")
    frames = [load_wave(w) for w in WAVES]
    panel = pd.concat(frames, ignore_index=True)
    print(f"    → long 패널: {len(panel):,}행 "
          f"(사람 {panel.person_id.nunique():,}명 × 웨이브 {len(WAVES)})")

    print("\n[2] 결측코드 정리")
    for c in panel.columns:
        if c in ("person_id", "wave", "year"):
            continue
        if pd.api.types.is_numeric_dtype(panel[c]):
            panel.loc[panel[c].isin(MISSING), c] = np.nan

    print("[3] 소득 월평균 환산 (시급/일급/주급 → 월급)")
    panel["income_now"] = to_monthly_income(
        panel.get("income_amount"), panel.get("income_unit"),
        panel.get("work_hours"), panel.get("work_days"),
    )
    # 비임금근로자는 income_self로 보완
    if "income_self" in panel:
        panel["income_now"] = panel["income_now"].fillna(
            pd.to_numeric(panel["income_self"], errors="coerce"))
    panel.loc[~panel["income_now"].between(INCOME_MIN, INCOME_MAX),
              "income_now"] = np.nan
    n_ok = panel["income_now"].notna().sum()
    print(f"    유효 소득: {n_ok:,}행 / 중앙값 "
          f"{panel['income_now'].median():.0f}만원 (명목)")

    # [3-1] 실질소득 환산 — 웨이브가 2021~2024로 4년 걸쳐 있어 명목 그대로 두면
    #       매칭 풀(L2)·궤적(L5)에 서로 다른 화폐가치가 섞이고, 소득 증가율에
    #       물가상승분이 성장으로 잡힌다. KLIPS 와 같은 CPI 표·기준연도를 쓴다.
    cpi = load_cpi()
    panel["income_now_nominal"] = panel["income_now"]
    panel["income_now"] = (panel["income_now"]
                           * panel["year"].map(lambda y: cpi[CPI_BASE_YEAR] / cpi[int(y)])
                           ).round(1)
    print(f"    실질소득(기준 {CPI_BASE_YEAR}년) 중앙값 "
          f"{panel['income_now'].median():.0f}만원 · "
          f"연도별 {panel.groupby('year')['income_now'].median().round(0).to_dict()}")

    print("[4] 이직 이벤트 플래그")
    # 그만둔 시기(job_end_y)가 있으면 그 웨이브에 이직 발생
    panel["changed_job"] = panel["job_end_y"].notna().astype(int)
    print(f"    이직 발생 관측: {panel.changed_job.sum():,}건")

    panel["survey"] = "YP2021"
    return panel


def build_spells(panel: pd.DataFrame) -> pd.DataFrame:
    """★L4 생존분석용 — (duration_months, event) 생성.

    ★중요 — B섹션과 C섹션은 '서로 다른 일자리'다:
        C섹션(y**c101) = 지금 다니는 직장의 시작 시점
        B섹션(y**b136) = 지난 조사 이후 '그만둔' (이전) 직장의 종료 시점
      이 둘을 한 spell로 묶으면 안 됨(이전 버전의 버그 →
      '이직자 근속 중앙값 0개월'이라는 불가능한 값이 나왔던 원인).

    올바른 방법:
      한 사람의 '현 직장'을 웨이브별로 추적한다.
        · 어느 웨이브에서 job_start(입사시점)가 바뀌면 → 직장을 옮긴 것(event=1)
          그 이전 직장의 근속 = 새 입사시점 − 이전 입사시점
        · 마지막까지 job_start가 그대로면 → 아직 재직중(censored, event=0)
          근속 = 마지막 조사시점 − 입사시점
    """
    print("\n[5] spell 생성 (L4 생존분석용)")

    def ym(y, m):
        y = pd.to_numeric(y, errors="coerce")
        m = pd.to_numeric(m, errors="coerce").fillna(6)   # 월 결측 → 연중값
        return y * 12 + m

    p = panel.copy()
    p["start_ym"] = ym(p["job_start_y"], p["job_start_m"])
    p["obs_ym"] = p["year"] * 12 + 6      # 조사 시점(연중 가정)

    rows = []
    for pid, g in p.sort_values("wave").groupby("person_id"):
        g = g[g["start_ym"].notna()]
        if g.empty:
            continue

        # 같은 직장이 연속된 웨이브에 나오면 start_ym이 동일 → 변할 때가 '이직'
        recs = g[["wave", "start_ym", "obs_ym"]].to_dict("records")
        for i, cur in enumerate(recs):
            nxt = recs[i + 1] if i + 1 < len(recs) else None

            if nxt is None:
                # 마지막 관찰 → 아직 재직중(censored)
                dur, event = cur["obs_ym"] - cur["start_ym"], 0
            elif nxt["start_ym"] > cur["start_ym"]:
                # 다음 웨이브에 입사시점이 바뀜 → 이 직장을 떠났다(event)
                dur, event = nxt["start_ym"] - cur["start_ym"], 1
            else:
                continue      # 같은 직장 계속 → spell 아직 진행중, 건너뜀

            if pd.isna(dur) or dur < 0 or dur > 240:
                continue

            row = g[g.wave == cur["wave"]].iloc[0]
            rows.append({
                "person_id": pid,
                "wave": cur["wave"],
                "duration_months": float(dur),
                "event": event,
                "age": row.get("age"),
                "sex": row.get("sex"),
                "edu_level": row.get("edu_level"),
                "occupation_raw": row.get("occupation_raw"),
                "firm_size": row.get("firm_size"),
                "emp_status": row.get("emp_status"),
                "income_now": row.get("income_now"),
                "satis_stability": row.get("satis_stability"),
                "satis_growth": row.get("satis_growth"),
            })

    sp = pd.DataFrame(rows)
    if len(sp):
        ev = sp[sp.event == 1]
        print(f"    spell {len(sp):,}건 | 이직(event=1) {sp.event.sum():,}건 "
              f"({sp.event.mean()*100:.1f}%) | censored {(sp.event==0).sum():,}건")
        print(f"    전체 근속 중앙값   {sp.duration_months.median():.0f}개월")
        if len(ev):
            print(f"    이직자 근속 중앙값 {ev.duration_months.median():.0f}개월 "
                  f"(★0이면 여전히 버그)")
    return sp


def main():
    panel = build_panel()
    verify_codes(panel)
    spells = build_spells(panel)

    OUT_PANEL.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(OUT_PANEL, index=False, encoding="utf-8-sig")
    print(f"\n[6] 저장 → {OUT_PANEL} ({len(panel):,}행 × {panel.shape[1]}열)")
    if len(spells):
        spells.to_csv(OUT_SPELL, index=False, encoding="utf-8-sig")
        print(f"        → {OUT_SPELL} ({len(spells):,}행)")

    # 타겟 커버리지
    if "age" in panel:
        t = panel[panel.age.between(25, 35)]
        print(f"\n[7] 타겟 25~35세: {len(t):,}행 "
              f"({t.person_id.nunique():,}명) "
              f"| 연령 중앙값 {panel.age.median():.0f}세")
        print("    ※GOMS(26세 집중)의 30대 공백을 YP가 메우는지 확인할 것")


if __name__ == "__main__":
    main()