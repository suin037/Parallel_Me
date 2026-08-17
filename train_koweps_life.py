"""KOWEPS 생활사건 처치효과 — 결혼·자가전환·이사. 커리어 밖 선택을 처음으로 받는다.

## 왜
분류기에 있는 유형은 이직·창업·진학·휴식·유지 5종뿐이라, 시연에서 나올 법한 입력
22개를 넣어보면 절반 이상이 `기타`로 빠진다. 빠진 것들의 정체는 대부분 **커리어가
아닌 인생 선택**이다.

    결혼할까 · 집을 살까 · 이사갈까 · 아이를 가질까 · 부모님과 합칠까

이건 키워드를 더 넣어서 될 문제가 아니라 유형 자체가 없는 문제였다. 그런데 KOWEPS
시나리오 패널에는 이 사건들의 표본이 이미 있고, 전부 게이트(200)를 넉넉히 넘는다.

    결혼 902명 · 자가전환 1,213명 · 이사 2,603명   (25~35세 최초사건 기준)

`train_koweps_startup.py` 의 뼈대를 그대로 쓰고 처치 정의만 바꾼다. 두 스크립트가
같은 열 캐시(`COLUMNS`)를 공유하므로 1.4GB Long Form 을 다시 읽지 않는다.

## 처치 정의 (연속 차수 t → t+1)
| 유형 | 변수 | 처치 | 대조 |
|---|---|---|---|
| 결혼 | `h_g10` 혼인상태 | 5(미혼) → 1(유배우) | 미혼 유지 |
| 자가 | `h06_3` 점유형태 | 2·3·4·5(임차) → 1(자가) | 임차 유지 |
| 이사 | `h06_aq1` 지난 1년 이사 | t+1 에 '그렇다' | '아니다' |

`h06_3` 코딩(1=자가 2=전세 3=보증부월세 4=월세 5=기타)은 코드북에 있다. `h_g10` 은
레지스트리에 "공식 값표 최종 대조 필요"로 적혀 있어 전이행렬로 확인했다 — 미혼(5)에서
나가는 전이 중 유배우(1)행이 1,194건으로 압도적이고 나머지는 두 자릿수다.

이사는 상태 전이가 아니라 **'지난 1년에 이사했는가'** 문항이라, t+1 시점 응답이 곧
t→t+1 사이의 사건이다. 그래서 t+1 응답으로 처치를 가르고 공변량은 t 에서 읽는다.

## 결과변수는 사건마다 다르다
결혼에 주거만족을, 이사에 가족만족을 붙이면 관계없는 축을 재게 된다. 사건별로
'그 선택이 실제로 건드리는 축'만 고른다(아래 `TREATMENTS[...]["outcomes"]`).

주거만족(`p03_7`)·가족만족(`p03_8`)은 전반만족과 +0.46 내외, 소득과 +0.14~0.17 로
**정방향**임을 확인했다(역코딩 불필요). 건강·우울은 startup 쪽과 같은 역코딩을 쓴다.

사회관계만족(`p03_10`)도 같은 방식으로 확인했다 — 전반만족 +0.550, 가구소득 +0.157
(유효관측 247,038). 정방향이라 역코딩하지 않는다. 관계 영역에서 **가족 밖 친분관계**를
재는 유일한 축이라, 결혼·이사처럼 사람 관계망이 실제로 바뀌는 사건에만 붙인다.
자가 전환은 점유형태만 바뀌는 사건이라 붙이지 않는다.

## ⚠ 이 수치의 성격
가구 가처분소득(`h_din`)은 **가구 단위**다. 결혼은 정의상 가구 구성이 바뀌는 사건이라
소득 증가분의 상당 부분이 '배우자 소득이 가구에 합쳐진 것'이다 — 개인이 더 벌게
됐다는 뜻이 아니다. 결혼의 소득 효과는 특히 이렇게 읽어야 한다.

산출:
    backend/models/artifacts/koweps_life_effects.json

사용법:
    python train_koweps_life.py
    python train_koweps_life.py --horizon 3
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import pandas as pd

import train_koweps_startup as SU

ARTIFACTS = SU.ARTIFACTS
OUT_PATH = ARTIFACTS / "koweps_life_effects.json"

# 결과변수 메타 — startup 쪽과 같은 계약(클수록 좋음으로 통일).
OUTCOMES = {
    "주거만족": {"src": "p03_7", "unit": "점(1~5)", "top": 5, "reverse": False,
                 "scale": "likert5", "level": "개인",
                 "note": "정방향 — 전반만족과 +0.457 상관으로 확인"},
    "가족만족": {"src": "p03_8", "unit": "점(1~5)", "top": 5, "reverse": False,
                 "scale": "likert5", "level": "개인",
                 "note": "정방향 — 전반만족과 +0.469 상관으로 확인"},
    "사회관계만족": {"src": "p03_10", "unit": "점(1~5)", "top": 5, "reverse": False,
                     "scale": "likert5", "level": "개인",
                     "note": ("정방향 — 전반만족과 +0.550, 가구소득과 +0.157 상관으로 확인"
                              "(유효관측 247,038). 가족 밖 친분관계 축이라 가족만족과 짝을 "
                              "이룬다")},
    "전반만족": SU.OUTCOMES["전반만족"],
    "정신건강": SU.OUTCOMES["정신건강"],
    "건강": SU.OUTCOMES["건강"],
    "가처분소득": SU.OUTCOMES["가처분소득"],
}

TREATMENTS = {
    "결혼": {
        "source": "h_g10", "mode": "transition", "from": [5], "to": [1],
        "label": "미혼 유지 vs 결혼",
        "coding": "5=미혼 → 1=유배우. 전이행렬로 확인(5→1 이 1,194건으로 압도적)",
        "outcomes": ["가족만족", "사회관계만족", "전반만족", "정신건강", "가처분소득"],
        "caveat": ("가구 가처분소득 증가분의 상당 부분은 **배우자 소득이 가구에 "
                   "합쳐진 것**이지 개인이 더 벌게 됐다는 뜻이 아니다. 결혼은 정의상 "
                   "가구 구성이 바뀌는 사건이라 이 축은 특히 조심해서 읽어야 한다."),
    },
    "자가": {
        "source": "h06_3", "mode": "transition", "from": [2, 3, 4, 5], "to": [1],
        "label": "임차 유지 vs 자가 전환",
        "coding": "1=자가 2=전세 3=보증부월세 4=월세 5=기타 (코드북 명시)",
        "outcomes": ["주거만족", "전반만족", "정신건강", "가처분소득"],
        "caveat": ("자가 전환은 대개 대출을 동반한다. 가처분소득에는 원리금 상환이 "
                   "반영되지 않으므로 '집을 사면 여유가 이만큼 는다'로 읽으면 안 된다. "
                   "또한 살 수 있는 사람이 사는 것이라 미관측 자산이 남는다."),
    },
    "이사": {
        "source": "h06_aq1", "mode": "yes", "yes": 1, "no": 2,
        "label": "현재 거주 유지 vs 이사",
        "coding": "1=그렇다 2=아니다 ('지난 1년 이사' 문항)",
        "outcomes": ["주거만족", "사회관계만족", "전반만족", "정신건강"],
        "caveat": ("자발적 이사(더 나은 집으로)와 비자발적 이사(계약 만료·경제 사정)가 "
                   "구분되지 않는다. 문항이 이유를 묻지 않으므로 두 방향이 상쇄될 수 "
                   "있고, 그 경우 '효과 없음'은 '아무 일도 안 일어난다'가 아니다."),
    },
}


def transition_frame(df: pd.DataFrame, key: str, outcome: str, horizon: int,
                     age_band: tuple[int, int]) -> pd.DataFrame:
    """t 공변량 + t→t+1 사건 + t+horizon 결과. 처치·대조 외의 행은 버린다."""
    spec = TREATMENTS[key]
    meta = OUTCOMES[outcome]
    d = df.sort_values(["h_pid", "wv"]).copy()
    d["_y"] = SU.clean_outcome(d[meta["src"]], meta)
    g = d.groupby("h_pid", sort=False)
    src_next = g[spec["source"]].shift(-1)
    nxt_wv = g["wv"].shift(-1)
    out_y = g["_y"].shift(-horizon)
    out_wv = g["wv"].shift(-horizon)

    frame = pd.DataFrame({
        "pid": d["h_pid"],
        "age": d["age"], "sex": d["h_g3"], "edu": d["h_g6"],
        "income_now": d["h_din"], "occ": d["h_eco9"],
        "work_hours_type": d["h_eco6"], "household_size": d["h01_1"],
        "outcome_now": d["_y"],
        "src_now": d[spec["source"]], "src_next": src_next,
        "gap1": nxt_wv - d["wv"], "gap_h": out_wv - d["wv"],
        "y": out_y,
    })
    frame = frame[(frame["gap1"] == 1) & (frame["gap_h"] == horizon)]

    if spec["mode"] == "transition":
        # 처치 = from → to, 대조 = from 유지. 다른 상태로 간 행은 이 A/B 질문의
        # 비교군이 아니다(예: 미혼 → 사별은 '결혼할까'의 대조가 아니다).
        at_risk = frame["src_now"].isin(spec["from"])
        frame = frame[at_risk & frame["src_next"].isin([*spec["to"], *spec["from"]])]
        frame["T"] = frame["src_next"].isin(spec["to"]).astype(int)
    else:                                    # mode == "yes"
        # '지난 1년 이사' 는 t+1 응답이 곧 t→t+1 사이의 사건이다.
        frame = frame[frame["src_next"].isin([spec["yes"], spec["no"]])]
        frame["T"] = frame["src_next"].eq(spec["yes"]).astype(int)

    frame = frame.dropna(subset=["y", "age", "sex", "edu", "income_now"])
    frame = frame[frame["age"].between(*age_band)]
    for c in ("occ", "work_hours_type", "household_size"):
        frame[c] = frame[c].fillna(frame[c].median())
    return frame


def measure(df, key: str, outcome: str, horizon: int, age_band) -> dict | None:
    d = transition_frame(df, key, outcome, horizon, age_band)
    if OUTCOMES[outcome]["level"] == "가구":
        # 가구소득은 W 의 income_now 가 곧 직전 Y 라 이미 통제돼 있다.
        return SU.fit(d, SU.W_COLS, f"[{key} × {outcome}]")
    main = SU.fit(d.dropna(subset=["outcome_now"]), [*SU.W_COLS, "outcome_now"],
                  f"[{key} × {outcome}]")
    if main is not None:
        main["baseline_controlled"] = True
    return main


def main() -> None:
    ap = argparse.ArgumentParser(description="KOWEPS 생활사건 처치효과")
    ap.add_argument("--horizon", type=int, default=1)
    args = ap.parse_args()

    df = SU.load_columns()
    report = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source": "KOWEPS 1~20차 (2006~2025) Long Form",
        "horizon": args.horizon,
        "estimator": "LinearDML (RF nuisance, 분석적 95% CI)",
        "min_treated": SU.MIN_TREATED,
        "x_cols": SU.X_COLS, "w_cols": SU.W_COLS,
        "outcomes": OUTCOMES,
        "note": ("소득 외 결과변수는 t 시점 같은 문항(outcome_now)을 W 에 넣은 "
                 "직전 Y 통제본이다. 커리어 예측(L2 유사인물·L5 소득궤적)은 이 "
                 "선택들에 적용되지 않는다 — 여기서 내는 건 처치효과뿐이다."),
        "treatments": {},
    }

    for key, spec in TREATMENTS.items():
        entry = {"label": spec["label"], "coding": spec["coding"],
                 "caveat": spec["caveat"], "bands": {}}
        for band in [(20, 45), (20, 39)]:
            bkey = f"{band[0]}-{band[1]}"
            print(f"\n=== {key} — 연령 {bkey} (t+{args.horizon}) ===")
            got = {}
            for outcome in spec["outcomes"]:
                if (res := measure(df, key, outcome, args.horizon, band)) is not None:
                    got[outcome] = res
            entry["bands"][bkey] = got
        report["treatments"][key] = entry

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n[done] → {OUT_PATH}")


if __name__ == "__main__":
    main()
