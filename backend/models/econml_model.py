"""EconML: 선택이 소득에 미치는 인과효과 추정.

v5: **treatment 축을 추가**했다. 기존엔 '이직' 하나뿐이라 함수가 사실상 이직 전용
    이었고, 창업/진학은 개인단위 인과가 통째로 없었다. 이제 treatment 별로 artifact
    를 고른다(`train_treatments.py` 산출).

    · move    (이직) — 청년 econml_yp.pkl / 그 외 econml_klips.pkl / 폴백 econml.pkl
    · startup (창업) — econml_klips_startup.pkl (KLIPS 임금근로→자영 전이)
    · break   (쉬어가기) — econml_klips_break.pkl (자발 퇴직 후 2개월 이상 공백)
              **복귀한 사람만** 결과가 관측된다 → L4 복귀기간과 함께 읽을 것.
    · enroll  (진학) — **artifact 없음**. 학력상승 전이가 학습 최소표본에 못 미쳐
                       모델을 만들지 않았다(근거는 artifacts/treatment_report.json).

연령 라우팅(청년→YP)은 이직에만 적용된다. 창업은 KLIPS 만 있어 라우팅 대상이 없다.

YP/KLIPS artifact 는 medians 를 자체 포함하므로 enc = art 로 둔다.
GOMS 폴백만 encoders.pkl 을 별도로 쓴다.
"""

import logging
from functools import lru_cache

import joblib
import numpy as np

from config import settings

log = logging.getLogger(__name__)

# 열다가 실패한 artifact — {파일명: "예외타입: 메시지"}. lifelines_model 과 같은 이유로 남긴다.
_LOAD_ERRORS: dict[str, str] = {}


def load_errors() -> dict[str, str]:
    """로딩에 실패한 artifact 와 그 이유. 비어 있으면 전부 정상."""
    _load_all()
    return dict(_LOAD_ERRORS)


# YP(청년패널) 표본 상한(≈31세). 이 나이 이하 입력은 YP 모델을 우선 사용한다.
YOUTH_MAX = 31

# treatment → {소스키: artifact 파일명}. 소스키는 연령 라우팅에 쓰인다.
TREATMENT_FILES: dict[str, dict[str, str]] = {
    "move": {"yp": "econml_yp.pkl", "klips": "econml_klips.pkl",
             "goms": "econml.pkl"},
    "startup": {"klips": "econml_klips_startup.pkl"},
    "break": {"klips": "econml_klips_break.pkl"},
    # "enroll" 은 의도적으로 비어 있다 — 표본 부족으로 학습하지 않음
}


@lru_cache(maxsize=1)
def _load_all() -> dict:
    """사용 가능한 인과 artifact 전부. {treatment: {source: (art, enc)}}."""
    A = settings.artifacts_abspath
    out: dict[str, dict] = {}
    for treatment, files in TREATMENT_FILES.items():
        found: dict[str, tuple] = {}
        for key, fname in files.items():
            p = A / fname
            if not p.exists():
                continue
            # 파일 하나가 못 열려도 나머지 소스는 살린다(폴백 순서가 있으므로
            # 하나를 잃어도 답은 나온다). 예외를 그대로 올리면 _load_all() 전체가
            # 죽어 정상 artifact 까지 사라지고, 화면엔 이유 없이 데모 숫자가 뜬다.
            try:
                art = joblib.load(p)
                # GOMS 폴백만 encoders 별도, 종단 artifact 는 medians 자체 포함
                enc = joblib.load(A / "encoders.pkl") if key == "goms" else art
            except Exception as exc:
                log.warning("econml artifact '%s' 로딩 실패 — 이 소스만 건너뛴다: %s: %s",
                            fname, type(exc).__name__, exc)
                _LOAD_ERRORS[fname] = f"{type(exc).__name__}: {exc}"
                continue
            found[key] = (art, enc)
        if found:
            out[treatment] = found
    return out


def available_treatments() -> list[str]:
    """개인단위 인과(L3)를 제공할 수 있는 treatment 목록."""
    return sorted(_load_all())


def _select(features: dict, treatment: str = "move") -> tuple:
    """treatment + 연령대에 맞는 (art, enc) 선택."""
    arts = _load_all().get(treatment)
    if not arts:
        raise RuntimeError(f"'{treatment}' 인과 artifact 가 없습니다.")
    age = features.get("age")
    youth = age is not None and float(age) <= YOUTH_MAX
    order = ("yp", "klips", "goms") if youth else ("klips", "yp", "goms")
    for key in order:
        if key in arts:
            return arts[key]
    return next(iter(arts.values()))


def _value(col: str, features: dict, enc: dict) -> float:
    med = enc.get("medians", {})
    if col in ("age", "age_start"):
        return float(features.get("age", med.get(col, 30)))
    if col == "sex":                       # 종단 모델: 1/2 숫자
        try:
            return float(features.get("sex"))
        except (TypeError, ValueError):
            return med.get(col, 1)
    if col == "sex_enc":                   # GOMS 인코딩
        return enc["sex_map"].get(str(features.get("sex")), 0)
    if col == "major_enc":
        return enc["major_map"].get(str(features.get("major")), 0)
    v = features.get(col)
    return med.get(col, 0) if v is None else float(v)


def estimate_effect(features: dict, treatment: str = "move") -> float:
    """이 프로필에서 treatment 의 소득 인과효과(만원).

    처치군이 작은 artifact(`prefer_linear`)는 **개인별 이질효과를 쓰지 않는다.**
    CausalForest 는 n_treated 703(창업)에서도 개인 구간이 -348~+438 만원까지 벌어져
    개인화된 숫자를 내면 정밀해 보이는 잡음을 파는 셈이 된다 → 전체 ATE 를 그대로 쓴다.
    """
    art, enc = _select(features, treatment)
    if art.get("prefer_linear") and art.get("linear_ate") is not None:
        return float(art["linear_ate"])
    X = np.array([[_value(c, features, enc) for c in art["x_cols"]]], dtype=float)
    return float(art["model"].effect(X)[0])


def effect_source(features: dict, treatment: str = "move") -> str:
    """디버그/설명용: 이 입력에 어떤 소스가 쓰였는지."""
    art, _ = _select(features, treatment)
    return str(art.get("source", "unknown"))


def effect_confidence(features: dict, treatment: str = "move") -> dict | None:
    """이 입력에 쓰인 L3 인과모델의 신뢰지표(ATE 95% CI 등). 없으면 None.

    **LinearDML 의 analytic 95% CI 를 우선 노출**한다.
    CausalForestDML 의 ATE 구간(ate_ci)은 표본 분산이 커서 0을 포함할 만큼 넓게 나오는데,
    같은 데이터의 LinearDML CI(linear_ci)는 훨씬 정밀하다(점추정은 둘이 사실상 동일).
    예) YP: CForest ATE +27.1 (CI -20.7~+75.0) vs LinearDML +27.8 (CI +21.0~+34.6).
    → '인과효과가 0과 구분되는가'는 LinearDML CI 로 판단하는 게 정직·정확.

    `caveat` 가 있으면 그대로 실어 보낸다(창업처럼 결과변수 개념이 대조군과 다른 경우).
    """
    try:
        art, _ = _select(features, treatment)
    except RuntimeError:
        return None

    if art.get("linear_ate") is not None:
        ci = art.get("linear_ci") or (None, None)
        base = {"ate": round(float(art["linear_ate"]), 1),
                "method": "LinearDML (analytic 95% CI)"}
    elif art.get("ate") is not None:        # 폴백: CausalForestDML ATE 구간(넓음)
        ci = art.get("ate_ci") or (None, None)
        base = {"ate": round(float(art["ate"]), 1),
                "method": "CausalForestDML (ATE 구간, 넓음)"}
    else:
        return None

    return {
        **base,
        "ci95_low": round(float(ci[0]), 1) if ci[0] is not None else None,
        "ci95_high": round(float(ci[1]), 1) if ci[1] is not None else None,
        "unit": "만원",
        "treatment": treatment,
        "n": art.get("n"),
        "n_treated": art.get("n_treated"),
        "source": art.get("source"),
        "caveat": art.get("caveat"),
    }
