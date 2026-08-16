"""KLIPS 직업력(job history) 원본 → 일자리 스펠 + '쉬어가기' 스펠.

`preprocess_klips.py` 는 개인파일(`klips{w}p.sav`)만 읽는다. 개인파일은 조사 시점의
단면이라 **일자리를 언제 그만뒀는지, 왜 그만뒀는지, 다음 일자리까지 몇 달 비었는지**가
없다. 그 정보는 전부 직업력 파일(`klips{w}w.sav`)에 있고 지금까지 쓰이지 않았다.

    data/raw/klips/klips_jobspell.pkl       일자리 스펠 (pid × jobseq)
    data/raw/klips/klips_break.pkl          '쉬어가기' 스펠 (일자리 사이의 공백)
    data/raw/klips/klips_jobhist_report.json 빌드 메타

## 왜 필요한가
휴직·퇴사('잠시 쉬어갈까')를 판단해주려면 두 가지를 알아야 한다.

  1. **자발적으로 그만둔 사람만 볼 것.** 해고당한 사람의 결과를 섞으면
     "쉬어도 될까요?" 에 잘린 사람의 사정을 섞어서 답하게 된다.
  2. **얼마나 쉬게 되는지.** 파동(1년) 단위로는 "1년 쉬었다"까지만 보인다.
     직업력 파일은 취업·퇴직 시점이 **년/월**이라 공백을 달 단위로 잰다.

## 원본 파일
직업력 파일은 **누적**이다 — 27차 파일 하나에 1~27차에서 발견된 모든 일자리가 있다
(`jobwave` = 그 일자리가 발견된 차수). 그래서 최신 차수 파일 하나만 읽는다.

행 단위는 (pid, jobwave, jobseq) — 같은 일자리가 계속되면 파동마다 한 줄씩 쌓인다.
`jobseq` 가 파동을 가로지르는 일자리 고유번호이므로 이걸로 접는다.

| 컬럼 | 변수 | 비고 |
|---|---|---|
| 일자리ID | `jobseq` | 파동 불변. `jobnum` 은 파동별이라 쓰면 안 된다 |
| 취업시기 | `j001` / `j002` | 년 / 월. 같은 jobseq 안에서 불변 |
| 퇴직시기 | `j004` / `j005` | 년 / 월. **끝난 파동의 행에만** 채워진다 |
| 퇴직이유 | `j601` | 1=비자발 2=자발 (아래 검증 참고) |
| 구체적사유 | `j602` | 임금근로 한정. 14+ 코드 |
| 일자리형태 | `jobtype` | 임금 / 비임금 |
| 중도절단 | `jobcens` | 1=계속중 2=종료 3=이번 파동 신규 |

## j601 코드값 — .sav 에 값 라벨이 없어 실증으로 확정했다
한국 고용보험은 자발적 이직에 원칙적으로 실업급여를 주지 않는다. 실업급여 수령기간
(`j614`) 이 있는 비율을 코드별로 보면 갈린다(27차 기준):

    j601 == 1 : n=12,890  실업급여 수령 15.65%   → 비자발
    j601 == 2 : n=32,452  실업급여 수령  3.13%   → 자발

`j602` 교차표도 같은 방향이다 — 코드 1~6(해고·폐업·계약만료 계열)은 85~93% 가
`j601==1` 에 몰리고, 7·9~13·18·20(개인사유 계열)은 1.5~4.8% 만 그렇다.

## '쉬어가기' 스펠 정의
일자리 k 가 끝난 달 → 일자리 k+1 이 시작한 달 사이의 공백.

- `break_months == 0` 이면 공백 없는 직접 이직이다. 쉬어간 게 아니다.
- 마지막 일자리가 끝났는데 다음 일자리가 없으면 **우측 중도절단**이다
  (아직 쉬는 중일 수도, 조사에서 빠졌을 수도 있다). `event=0` 으로 남긴다.
  이걸 '복귀 안 함'으로 세면 쉬는 기간이 실제보다 길게 추정된다.

사용법:
    python preprocess/preprocess_klips_jobhist.py
    python preprocess/preprocess_klips_jobhist.py --klips-dir ../KLIPS
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_KLIPS_DIR = Path("data/raw/klips")
DEFAULT_OUT = Path("data/raw/klips")
WAVE_YEAR_OFFSET = 1997          # 1차 = 1998

# j601 — 위 docstring 의 실업급여 검증으로 확정
EXIT_INVOLUNTARY = 1
EXIT_VOLUNTARY = 2

YEAR_MIN, YEAR_MAX = 1960, 2030   # 이 밖의 년도는 입력오류로 보고 버린다


def find_jobhist(klips_dir: Path) -> Path:
    """가장 최신 차수의 직업력 파일. 누적이라 하나만 있으면 된다."""
    files = sorted(klips_dir.glob("klips[0-9][0-9]w.sav"))
    if not files:
        raise FileNotFoundError(
            f"{klips_dir} 에 klips**w.sav (직업력 파일) 가 없다. "
            "개인파일(p) 과 달리 직업력은 w 파일이다 — 원본 배포본에 함께 들어 있다."
        )
    return files[-1]


def to_ym(year: pd.Series, month: pd.Series) -> pd.Series:
    """(년, 월) → 년*100+월. 하나라도 결측/범위밖이면 결측."""
    y = pd.to_numeric(year, errors="coerce")
    m = pd.to_numeric(month, errors="coerce")
    ok = y.between(YEAR_MIN, YEAR_MAX) & m.between(1, 12)
    return (y * 100 + m).where(ok)


def months_between(a: pd.Series, b: pd.Series) -> pd.Series:
    """ym 두 개의 개월 차이 (b - a)."""
    return (b // 100 - a // 100) * 12 + (b % 100 - a % 100)


def read_jobhist(path: Path) -> pd.DataFrame:
    import pyreadstat

    want = ["pid", "jobwave", "jobseq", "jobcens", "jobtype", "mainjob",
            "j001", "j002", "j004", "j005", "j601", "j602", "j614"]
    present = set(pyreadstat.read_sav(str(path), metadataonly=True)[1].column_names)
    if missing := [c for c in ("pid", "jobseq", "j001", "j004") if c not in present]:
        raise KeyError(f"{path.name} 에 {missing} 없음 — 직업력 파일이 맞는지 확인할 것")
    cols = [c for c in want if c in present]

    raw, _ = pyreadstat.read_sav(str(path), usecols=cols)
    d = pd.DataFrame({"pid": raw["pid"]})
    for c in cols:
        if c == "pid":
            continue
        # KLIPS 무응답은 음수 코딩
        d[c] = pd.to_numeric(raw[c], errors="coerce").mask(lambda s: s < 0)
    return d


def collapse_spells(d: pd.DataFrame) -> pd.DataFrame:
    """(pid, jobwave, jobseq) 관측들을 (pid, jobseq) 일자리 하나로 접는다.

    취업시기는 파동 간 불변이라 첫 관측을 쓰고, 퇴직시기·퇴직이유는 끝난 파동에만
    있으므로 결측이 아닌 값을 집는다.
    """
    d = d.copy()
    d["start_ym"] = to_ym(d["j001"], d["j002"])
    d["end_ym"] = to_ym(d["j004"], d["j005"])

    first = lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan   # noqa: E731
    last = lambda s: s.dropna().iloc[-1] if s.notna().any() else np.nan   # noqa: E731

    g = d.sort_values(["pid", "jobseq", "jobwave"]).groupby(["pid", "jobseq"], sort=False)
    out = g.agg(
        start_ym=("start_ym", first),
        end_ym=("end_ym", last),
        exit_code=("j601", last),
        exit_reason=("j602", last) if "j602" in d else ("j601", last),
        jobtype=("jobtype", first) if "jobtype" in d else ("jobseq", first),
        mainjob=("mainjob", "max") if "mainjob" in d else ("jobseq", first),
        last_wave=("jobwave", "max"),
        n_waves=("jobwave", "size"),
    ).reset_index()

    out = out[out["start_ym"].notna()]
    # 퇴직이 취업보다 앞서면 입력오류 — 스펠을 못 믿으니 종료를 비운다
    bad_order = out["end_ym"].notna() & (out["end_ym"] < out["start_ym"])
    out.loc[bad_order, "end_ym"] = np.nan
    out["ended"] = out["end_ym"].notna()
    out["tenure_months"] = months_between(out["start_ym"], out["end_ym"])
    return out.sort_values(["pid", "start_ym"]).reset_index(drop=True)


def build_breaks(spells: pd.DataFrame, last_obs_ym: pd.Series) -> pd.DataFrame:
    """일자리 사이의 공백 = '쉬어가기' 스펠.

    끝난 일자리마다 한 행. 다음 일자리가 관측되면 event=1(복귀), 아니면 0(중도절단).
    """
    s = spells.sort_values(["pid", "start_ym"]).copy()
    s["next_start_ym"] = s.groupby("pid", sort=False)["start_ym"].shift(-1)

    b = s[s["ended"]].copy()
    b["censor_ym"] = b["pid"].map(last_obs_ym)

    returned = b["next_start_ym"].notna() & (b["next_start_ym"] >= b["end_ym"])
    b["event"] = returned.astype(int)          # 1 = 복귀 관측, 0 = 우측 중도절단
    b["break_months"] = np.where(
        returned,
        months_between(b["end_ym"], b["next_start_ym"]),
        months_between(b["end_ym"], b["censor_ym"]),
    )
    # 중도절단인데 관측 종료가 퇴직보다 앞서면(조사 이탈) 기간을 못 잰다
    b = b[b["break_months"].notna() & (b["break_months"] >= 0)]

    b["voluntary"] = b["exit_code"].map(
        {EXIT_VOLUNTARY: True, EXIT_INVOLUNTARY: False}).astype("boolean")
    # 공백 0개월 = 쉬지 않고 바로 옮긴 직접 이직
    b["is_break"] = b["event"].eq(1) & b["break_months"].gt(0) | b["event"].eq(0)
    return b.reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="KLIPS 직업력 → 일자리·쉬어가기 스펠")
    ap.add_argument("--klips-dir", type=Path, default=DEFAULT_KLIPS_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    path = find_jobhist(args.klips_dir)
    print(f"직업력 파일: {path}")
    raw = read_jobhist(path)
    print(f"  원본 {len(raw):,}행 / {raw['pid'].nunique():,}명 "
          f"/ jobwave {int(raw['jobwave'].min())}~{int(raw['jobwave'].max())}")

    spells = collapse_spells(raw)
    print(f"  일자리 스펠 {len(spells):,}개 (종료 관측 {int(spells['ended'].sum()):,}개)")

    # 사람별 마지막 관측 시점 — 중도절단 기준. 그 차수 조사연도 12월로 둔다.
    last_obs_ym = (raw.groupby("pid")["jobwave"].max() + WAVE_YEAR_OFFSET) * 100 + 12

    breaks = build_breaks(spells, last_obs_ym)
    rest = breaks[breaks["is_break"]]
    vol = rest[rest["voluntary"] == True]      # noqa: E712
    vol_done = vol[vol["event"] == 1]

    print()
    print(f"쉬어가기 스펠 {len(rest):,}개")
    print(f"  ├ 자발적 퇴직        {len(vol):,}개")
    print(f"  ├ 비자발(해고 등)    {int((rest['voluntary'] == False).sum()):,}개")
    print(f"  └ 사유 무응답        {int(rest['voluntary'].isna().sum()):,}개")
    if len(vol_done):
        q = vol_done["break_months"].quantile([.25, .5, .75])
        print()
        print(f"  [자발·복귀 관측 {len(vol_done):,}건] 쉰 기간(개월)")
        print(f"    중앙값 {q[.5]:.0f}  /  IQR {q[.25]:.0f}~{q[.75]:.0f}")
        for cut in (3, 6, 12, 24):
            print(f"    {cut:>2}개월 이내 복귀 {vol_done['break_months'].le(cut).mean():6.1%}")

    args.out.mkdir(parents=True, exist_ok=True)
    spells.to_pickle(args.out / "klips_jobspell.pkl")
    breaks.to_pickle(args.out / "klips_break.pkl")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": path.name,
        "waves": [int(raw["jobwave"].min()), int(raw["jobwave"].max())],
        "rows_raw": int(len(raw)),
        "persons": int(raw["pid"].nunique()),
        "job_spells": int(len(spells)),
        "job_spells_ended": int(spells["ended"].sum()),
        "break_spells": int(len(rest)),
        "break_voluntary": int(len(vol)),
        "break_involuntary": int((rest["voluntary"] == False).sum()),
        "break_reason_missing": int(rest["voluntary"].isna().sum()),
        "break_voluntary_returned": int(len(vol_done)),
        "exit_code_meaning": {
            "1": "비자발 (실업급여 수령률 15.7%)",
            "2": "자발 (실업급여 수령률 3.1%)",
        },
        "break_months_quantiles": (
            {str(k): float(v) for k, v in
             vol_done["break_months"].quantile([.25, .5, .75]).items()}
            if len(vol_done) else {}
        ),
    }
    (args.out / "klips_jobhist_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"저장: {args.out/'klips_jobspell.pkl'}")
    print(f"      {args.out/'klips_break.pkl'}")
    print(f"      {args.out/'klips_jobhist_report.json'}")


if __name__ == "__main__":
    main()
