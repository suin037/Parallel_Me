"""FastAPI 엔트리포인트.

예측 코어는 core.run_prediction 에, A/B 비교는 compare.build_comparison 에 있고
여기선 라우팅만 한다.
  · POST /predict  — 현재의 나 + 선택 1개 → 평행우주 추정(L1~L5)
  · POST /compare  — 현재의 나 + 선택 A/B → 발표 카드용 비교 뷰(3지표×1·3·5·10)
  · POST /simulate — /compare 수치 + RAG 근거 + Claude 서사(전체 파이프라인)
"""

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import functools
import json
import logging
import os
import sys
import threading
import traceback

log = logging.getLogger("parallel-me")

import avatar_vision
from config import ROOT, settings
from schemas import (
    AvatarFromPhotoRequest,
    AvatarFromPhotoResponse,
    Profile,
    PredictRequest,
    PredictResponse,
    CompareRequest,
    CompareResponse,
    SimulateRequest,
    AvatarGenerateRequest,
    AvatarGenerateResponse,
)
import avatar_gen
from core import run_prediction
from compare import build_comparison
from choice_classifier import classification_stats

import stat_evidence
import usage_guard
import indicators as indicators_mod
import diary_bridge
import personalize
from utils.claude_api import generate_scenarios, warm_narrative_schema
from rag.psych_narrative import get_psych_evidence, build_psych_prompt_block
from rag import safety as rag_safety
from utils.cloudflare_images import generate_pair
from domain_router import route_domains
from models.job_change_candidate import financial_impact, prediction_for_choice
from koweps_evidence import (
    evidence_for_request as koweps_evidence_for_request,
    indicator_statuses as koweps_indicator_statuses,
)

# 삶의 영역(domain) key → 라벨. 프론트 LIFE_DOMAINS 와 1:1 (행동+영역 구조화 입력).
DOMAIN_LABELS = {
    "career": "직업", "education": "교육", "business": "사업", "finance": "재무",
    "health": "건강", "housing": "주거", "relationship": "관계",
    "lifestyle": "생활방식", "long_term_values": "장기 가치",
}


def _domain_labels(keys) -> list[str]:
    """domain key 리스트 → 라벨 리스트(모르는 key 는 그대로)."""
    return [DOMAIN_LABELS.get(k, k) for k in (keys or [])]


# ── 근거 수준(로드맵 항목4) ──────────────────────────────────────────────
# 응답이 '어떤 강도의 근거'인지 프론트에 명시 → 데이터 없는데 숫자 만드는 문제 방지.
EVIDENCE_LABEL = {
    "model": "모델예측",        # 개별·인과 모델 산출(econml 인과효과 / lifelines 생존)
    "group_stat": "집단통계",   # 유사집단 중앙값 궤적(GOMS/YP/KOSIS 등)
    "rag": "RAG설명",           # 수치 없이 심리·이론 근거만
    "insufficient": "데이터부족",  # 뒷받침 데이터 없음 → 숫자 만들지 않음
}

def _has_available(arr) -> bool:
    return any((p or {}).get("available") for p in (arr or []))


def _scenario_evidence(scen: dict, has_rag: bool) -> dict:
    """시나리오를 뒷받침하는 '가장 강한' 근거 수준 + 구성요소."""
    raw = scen.get("raw") or {}
    has_model = raw.get("causal_effect") is not None or raw.get("survival_months") is not None
    has_group = any(_has_available(scen.get(k))
                    for k in ("income", "satisfaction", "growth_potential", "regret"))
    level = ("model" if has_model else "group_stat" if has_group
             else "rag" if has_rag else "insufficient")
    return {"level": level, "label": EVIDENCE_LABEL[level],
            "components": {"model": has_model, "group_stat": has_group, "rag": bool(has_rag)}}


def _coverage_from_routes(routed: dict) -> dict:
    """route_domains 결과 → 수치 그래프 표시 정당성(그래프 가드). 라우터가 근거의 단일 소스."""
    # 정량 근거: career(모델) 또는 실제 지표가 잡힌 group_stat 영역이 하나라도 있어야 정당.
    quant = any(v["evidence"] == "model" or (v["evidence"] == "group_stat" and v["indicators"])
                for v in routed.values())
    return {
        "per_domain": {k: {"label": v["label"], "evidence": v["evidence"]} for k, v in routed.items()},
        "quantitative_ok": quant if routed else True,  # domain 미지정이면 기존대로 허용
        "guard_note": (None if (quant or not routed) else
                       "이 질문의 삶의 영역은 정량 예측 데이터가 없어요 — "
                       "수치 그래프 대신 통계·설명 근거로만 답합니다."),
    }


def _validated_prediction(kind: str, profile: dict) -> dict:
    """호환용 관측 경로가 없어도 핵심 L1~L5 비교를 실패시키지 않는다."""
    try:
        return prediction_for_choice(kind, profile)
    except (ImportError, FileNotFoundError, OSError, ValueError) as exc:
        log.warning("검증 관측경로 생략(%s): %s", kind, exc)
        return {
            "status": "unavailable",
            "reason": f"선택 보조 관측경로를 불러오지 못했습니다({type(exc).__name__})",
        }


app = FastAPI(title="parallel-me API")

# jy-model의 성향 분석/저장 API를 같은 백엔드 포트에서 제공한다.
# 선택 의존성 문제로 로딩하지 못해도 기존 예측 API는 계속 기동한다.
#
# 실패를 조용히 삼키면 안 된다 — 마운트가 깨지면 /qmode/* 전체(두 길의 하루·챗봇·
# 성향분석·기업분석·관계분석·주간리포트)가 404 가 되는데, 프론트는 그걸 "서버가
# 꺼져 있다"로 표시한다. 서버는 멀쩡히 떠 있으므로 원인을 찾을 단서가 없어진다.
# 그래서 (1) 스택을 로그에 남기고 (2) /health 에 마운트 상태를 노출한다.
QMODE_MOUNT: dict = {"mounted": False, "error": None}
try:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from diary_module.qmode.api import app as qmode_app

    app.mount("/qmode", qmode_app)
    QMODE_MOUNT["mounted"] = True
except Exception as exc:
    qmode_app = None
    QMODE_MOUNT["error"] = f"{type(exc).__name__}: {exc}"
    log.error("qmode 마운트 실패 — /qmode/* 전체가 404가 됩니다\n%s",
              traceback.format_exc())

# ── 기동 워밍업 ────────────────────────────────────────────────────────────
# 무거운 지연 로딩이 **첫 사용자 요청**에 얹히던 문제.
# 실측(워밍 후 /simulate 0.44s)과 달리 서버 기동 직후 첫 요청은 30초를 넘겼는데,
# 대부분이 심리카드 RAG 의 임베딩 모델(ko-sroberta) 로딩이었다. 엔진을 3.7배 빠르게
# 만들어도 이 앞에선 묻힌다 → 기동 시점에 미리 올려 서버 부팅 쪽으로 옮긴다.
#
# 백그라운드 스레드로 도는 이유: 블로킹하면 uvicorn 이 그동안 연결을 안 받아
# /health 조차 안 뜨고, --reload 개발 루프도 매번 느려진다. 온보딩을 채우는 동안
# 로딩이 끝나므로 사용자는 기다리지 않는다.
_warmup_state: dict = {"started": False, "done": False, "steps": {}}


def _warmup() -> None:
    import time as _t

    def step(name, fn):
        t0 = _t.perf_counter()
        try:
            fn()
            _warmup_state["steps"][name] = round(_t.perf_counter() - t0, 2)
        except Exception as exc:            # 워밍업 실패가 서버를 죽이면 안 된다
            _warmup_state["steps"][name] = f"실패: {type(exc).__name__}"
            log.warning("워밍업 '%s' 실패(요청 시 지연 로딩으로 폴백): %s", name, exc)

    import trajectory as _traj
    step("klips_panel", _traj._panel)
    step("yp_panel", _traj._yp_panel)
    step("artifacts", lambda: (
        __import__("models.econml_model", fromlist=["_load_all"])._load_all(),
        __import__("models.lifelines_model", fromlist=["_load_all"])._load_all()))
    # 가장 무거운 것 — 임베딩 모델 + 벡터DB
    step("psych_rag", lambda: get_psych_evidence(
        {"경제적안정도": 0.5, "성장가능성": 0.5, "삶의질": 0.5}, decision_type="이직"))
    # 서사의 구조화 출력 스키마는 처음 쓸 때 한 번 컴파일 비용을 낸다(이후 24h 캐시).
    # 그 비용도 첫 사용자에게서 기동 쪽으로 옮긴다. 키가 없으면 조용히 건너뛴다.
    step("narrative_schema", warm_narrative_schema)
    _warmup_state["done"] = True
    log.info("워밍업 완료: %s", _warmup_state["steps"])


@app.on_event("startup")
def _on_startup() -> None:
    if not settings.warmup_on_startup or _warmup_state["started"]:
        return
    _warmup_state["started"] = True
    threading.Thread(target=_warmup, name="warmup", daemon=True).start()


# CORS — 로컬 개발 포트는 늘 허용하고, 배포 프론트 주소는 환경변수로 더한다.
#
# 예전엔 regex 가 코드에 박혀 있어 http://localhost:포트 만 통과했다. 그대로 배포하면
# Vercel(https://…vercel.app) 에서 오는 요청이 전부 CORS 로 막히는데, 브라우저는
# "네트워크 오류" 로만 보여줘서 서버 로그에도 흔적이 안 남는다.
#
#   ALLOWED_ORIGINS   쉼표로 구분한 정확한 주소 목록. qmode/api.py 와 같은 이름을 쓴다
#                     (한 서버에 마운트돼 있어 이름이 갈리면 한쪽만 열리는 사고가 난다).
#   CORS_ORIGIN_REGEX 미리보기 배포처럼 주소가 매번 바뀔 때 쓰는 정규식(선택).
#                     예: https://.*\.vercel\.app
#
# iframe 임베드는 CORS 와 무관하다 — 그건 프론트를 감싸는 쪽 문제이고,
# 여기서 여는 건 브라우저가 이 API 를 직접 부를 수 있는 출처다.
_LOCAL_ORIGIN_RE = r"http://(localhost|127\.0\.0\.1):\d+"
_extra_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
_origin_regex = os.getenv("CORS_ORIGIN_REGEX", "").strip() or _LOCAL_ORIGIN_RE

app.add_middleware(
    CORSMiddleware,
    allow_origins=_extra_origins,          # 정확히 일치하는 배포 프론트 주소
    allow_origin_regex=_origin_regex,      # 로컬 포트(기본) 또는 지정한 패턴
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
log.info("CORS 허용 — origins=%s regex=%s", _extra_origins or "(없음)", _origin_regex)


def _simulate_without_artifacts(req, diary, safety_level) -> dict:
    """로컬 모델 파일이 없을 때 RAG+Claude 서사만 제공하는 개발용 폴백.

    ⚠ 예전엔 3지표를 전부 0.5 로 채워 넣고 그대로 심리카드를 검색했다.
    카드 검색은 '가장 낮은 지표'를 초점으로 잡고 그 지표의 버킷(낮음/중간/높음)으로
    카드를 거르는데, 0.5 셋은 **측정된 게 아니라 자리채우기**다. 그 위에서 뽑힌 카드는
    사용자와 아무 관계가 없으면서 근거처럼 보인다 — 근거수준 라벨만 '데이터부족'으로
    정직하고 정작 화면에 뜨는 카드는 그렇지 않았다.
    → 지표를 측정하지 못했으면 **카드 검색을 하지 않는다.** 지표도 0.5 가 아니라
      None 으로 내보내 '측정 못 함'과 '중간값'을 구분한다(프론트는 null 이면
      자체 파생 폴백을 쓴다).
    """
    psych_a = psych_b = {"focus_indicator": None, "level": None, "cards": [],
                         "skipped": "지표 미측정(아티팩트 부재) — 지표 기반 카드 검색 생략"}
    ev_a = stat_evidence.evidence_for_choice(req.choice_a)
    ev_b = stat_evidence.evidence_for_choice(req.choice_b)
    note_parts = [
        "개발용 폴백: 로컬 예측 모델 아티팩트가 없어 수치 예측은 제외하고, "
        "검색된 통계 근거와 사용자 입력만으로 서사를 작성한다. 숫자를 만들지 말 것. "
        "3지표를 측정하지 못해 심리 이론카드도 붙이지 않았다 — "
        "심리학적 해석을 지어내지 말 것."
    ]
    if req.choice_a_detail:
        note_parts.append(f"[사용자가 적은 A의 구체적 상황] {req.choice_a_detail}")
    if req.choice_b_detail:
        note_parts.append(f"[사용자가 적은 B의 구체적 상황] {req.choice_b_detail}")
    diary_line = diary_bridge.diary_context_line(diary)
    if diary_line:
        note_parts.append("[일기 신호] " + diary_line)
    # 심리근거 블록은 넣지 않는다 — 위에서 카드 검색 자체를 건너뛰었다.
    scen_a = {"choice": req.choice_a, "coverage": "RAG 서사 미리보기(수치 모델 제외)"}
    scen_b = {"choice": req.choice_b, "coverage": "RAG 서사 미리보기(수치 모델 제외)"}
    narrative = generate_scenarios(
        req.profile.model_dump(), scen_a, scen_b, ev_a, ev_b,
        note="\n\n".join(note_parts), model=settings.claude_model,
    )
    return {
        "profile": req.profile.model_dump(),
        "choice_a": req.choice_a,
        "choice_b": req.choice_b,
        "compare": None,
        # 0.5 자리채우기 대신 null — '측정 못 함'을 '중간값'으로 위장하지 않는다
        "indicators": {"A": None, "B": None},
        "indicators_measured": False,
        "psych": {"A": psych_a, "B": psych_b},
        "evidence": {"A": ev_a, "B": ev_b},
        "diary": diary,
        "safety_level": safety_level,
        "narrative": narrative,
        "api_used": not narrative.get("_skipped", False),
        "model": settings.claude_model,
        "fallback": "missing_prediction_artifacts",
    }


def _measured(scores: dict, detail: dict, override: dict | None) -> dict:
    """심리카드 검색에 넘길 지표만 남긴다(근거 없이 채운 중립값은 뺀다).

    전부 미측정이면 빈 dict → get_psych_evidence 가 카드 없이 돌려준다.
    요청이 직접 준 override 는 사용자가 책임지는 값이라 그대로 통과시킨다.
    """
    if override:
        return scores
    un = set((detail or {}).get("unmeasured") or [])
    return {k: v for k, v in scores.items() if k not in un}


@functools.lru_cache(maxsize=1)
def _artifact_manifest() -> dict:
    """서빙 중인 모델 아티팩트 명세(scripts/build_artifact_manifest.py 생성).

    training_report.json 만 보면 실제 서빙 구성(연령대별 YP/KLIPS 라우팅)을 알 수 없어
    실제로 두 파일이 어긋나 있었다 → 무엇이 서빙되는지 런타임에서 확인 가능하게 노출한다.
    """
    p = settings.artifacts_abspath / "manifest.json"
    if not p.exists():
        return {"available": False,
                "note": "python scripts/build_artifact_manifest.py 로 생성"}
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}"}
    artifacts = {}
    runtime_missing = []
    for name, entry in (m.get("artifacts") or {}).items():
        actual_present = (settings.artifacts_abspath / name).is_file()
        if not actual_present:
            runtime_missing.append(name)
        artifacts[name] = {
            **{k: entry[k] for k in ("layer", "source", "causal", "survival")
               if k in entry},
            "present": actual_present,
        }
    return {
        "available": True,
        "generated_at": m.get("generated_at"),
        "git": m.get("git"),
        "data_vintage": m.get("data_vintage"),
        "missing": runtime_missing,
        "manifest_missing": m.get("missing") or [],
        # 파일별 한 줄 요약(용량·features 등 상세는 manifest.json 원본 참조)
        "artifacts": artifacts,
    }


@functools.lru_cache(maxsize=1)
def _treatment_coverage() -> dict:
    """어떤 선택 유형에 개인단위 인과·생존이 붙는지 + 안 붙으면 그 근거(표본 수).

    '진학은 데이터가 없다' 를 가정이 아니라 **측정된 수치**로 말하기 위한 것.
    (train_treatments.py 가 만든 treatment_report.json)
    """
    p = settings.artifacts_abspath / "treatment_report.json"
    if not p.exists():
        return {"available": False, "note": "python train_treatments.py 로 생성"}
    try:
        r = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}"}
    return {
        "available": True,
        "built_at": r.get("built_at"),
        "age_band": r.get("age_band"),
        "min_treated": r.get("min_treated"),
        "treatments": {k: {kk: v[kk] for kk in
                           ("label", "n_treated", "trained", "reason", "linear_ate",
                            "linear_ci", "n_spells") if kk in v}
                       for k, v in (r.get("treatments") or {}).items()},
    }


@app.post("/evidence/koweps")
def koweps_evidence(payload: dict = Body(...)) -> dict:
    """선택 문장을 감사된 KOWEPS 사건 패널의 관측분포에 연결한다."""
    return koweps_evidence_for_request(payload)


@app.post("/avatar/generate", response_model=AvatarGenerateResponse)
def avatar_generate(req: AvatarGenerateRequest) -> AvatarGenerateResponse:
    """빌더 아바타(PNG)를 참조 이미지로 실사 아바타를 생성한다.

    실패해도 프론트는 SVG 아바타를 계속 쓰므로 화면이 깨지지 않는다.
    503 은 '설정/연동이 아직 안 됨', 400 은 '보낸 이미지가 잘못됨'.
    """
    try:
        return AvatarGenerateResponse(image=avatar_gen.generate(req.reference_png, req.prompt))
    except avatar_gen.AvatarGenError as e:
        # 참조 이미지 문제면 클라이언트 잘못, 그 외는 서버 설정 문제.
        status = 400 if "참조 이미지" in str(e) or "프롬프트" in str(e) else 503
        raise HTTPException(status_code=status, detail=str(e))


@app.get("/health")
def health() -> dict:
    # 선택 분류 통계·워밍업 상태는 캐시하지 않는다 — 런타임 값이라 매번 새로 읽는다.
    from rag import psych_retriever as _pr

    # qmode 또는 필수 모델 아티팩트가 빠지면 degraded 로 노출해 배포 단계에서 잡는다.
    artifact_state = _artifact_manifest()
    qmode = {**QMODE_MOUNT,
             "affects": "/qmode/* — 두 길의 하루·챗봇·성향분석·기업분석·관계분석·주간리포트"}
    degraded = (not QMODE_MOUNT["mounted"] or
                not artifact_state.get("available") or
                bool(artifact_state.get("missing")))
    return {"status": "degraded" if degraded else "ok",
            "model": settings.claude_model,
            "qmode": qmode,
            "warmup": {**_warmup_state, "psych_rag_loaded": _pr.is_loaded(),
                       "note": "done=false 면 첫 요청이 임베딩 모델 로딩(수십 초)을 "
                               "기다릴 수 있다"},
            "artifacts": artifact_state,
            "usage": usage_guard.status(),
            "treatment_coverage": _treatment_coverage(),
            "choice_classification": classification_stats()}


@app.post("/models/job-change/financial-impact")
def job_change_financial_impact(profile: Profile) -> dict:
    """검증된 집단 방향성과 실험적 개인 조건 추정치를 분리해 반환한다."""
    return financial_impact(profile.model_dump())


@app.post("/visualize")
async def visualize(
    avatar: UploadFile = File(...),
    choice_a: str = Form(...),
    choice_b: str = Form(...),
    narrative_a: str = Form(...),
    narrative_b: str = Form(...),
    future_years: int = Form(3),
    visual_width: int = Form(320),
    visual_height: int = Form(400),
    visual_format: str = Form("portrait 4:5"),
    avatar_spec: str = Form("{}"),
    visual_a: str = Form("{}"),
    visual_b: str = Form("{}"),
) -> dict:
    """동일 아바타를 참고해 RAG A/B 서사를 2D 장면 두 장으로 만든다."""
    if not narrative_a.strip() or not narrative_b.strip():
        raise HTTPException(400, "A/B narrative is required")
    allowed_sizes = {(320, 400), (512, 640), (768, 432)}
    if (visual_width, visual_height) not in allowed_sizes:
        raise HTTPException(422, "Unsupported visual image size")
    avatar_png = await avatar.read()
    if len(avatar_png) > 4 * 1024 * 1024:
        raise HTTPException(413, "Avatar image is too large")
    try:
        try:
            scene_a = json.loads(visual_a) if visual_a else {}
            scene_b = json.loads(visual_b) if visual_b else {}
            character_spec = json.loads(avatar_spec) if avatar_spec else {}
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "Visual scene direction must be valid JSON") from exc
        images = await generate_pair(
            avatar_png, choice_a, choice_b, narrative_a, narrative_b,
            scene_a, scene_b, character_spec, future_years,
            visual_width, visual_height, visual_format,
        )
    except Exception as exc:
        # 사유를 로그에도 남긴다. 예전에는 502 본문으로만 나가서 터미널에는
        # "502 Bad Gateway" 한 줄뿐이었고, Cloudflare 의 일시적 거절인지 설정 문제인지
        # 브라우저 개발자도구를 열기 전에는 구분할 수 없었다.
        # (httpx 전용 except 는 지웠다 — 이 경로는 requests 를 쓰므로 걸린 적이 없고,
        #  httpx.RequestError 에는 .response 가 없어 걸렸다면 AttributeError 가 났다.)
        log.error("이미지 생성 실패(%dx%d): %s", visual_width, visual_height, exc)
        raise HTTPException(502, str(exc)[:300]) from exc
    return {"images": images, "model": settings.cloudflare_reference_model}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    return run_prediction(req)


@app.post("/compare")
def compare(req: CompareRequest) -> dict:
    # 발표 카드용 수치 + 영역 라우팅/근거수준(항목3·4)을 함께 반환.
    # 프론트가 화면 수치를 /compare 에서 읽으므로 여기에도 실어야 표시된다.
    cmp = build_comparison(req).model_dump()
    # 라우터가 선택별로 갈리는 지표(창업 업종·규모별 생존율)를 뽑을 수 있도록
    # 각 쪽의 선택 문구를 프로필에 실어 보낸다. 공용 profile 만 넘기면 A·B 가
    # 같은 '전체 업종' 숫자를 받는다.
    routed_a = route_domains(getattr(req, "choice_a_domains", None), {
        **cmp["profile"], "choice": getattr(req, "choice_a_detail", None) or req.choice_a,
    })
    routed_b = route_domains(getattr(req, "choice_b_domains", None), {
        **cmp["profile"], "choice": getattr(req, "choice_b_detail", None) or req.choice_b,
    })
    cmp["domain_stats"] = {"A": routed_a, "B": routed_b}
    cmp["domain_coverage"] = {"A": _coverage_from_routes(routed_a),
                              "B": _coverage_from_routes(routed_b)}
    cmp["evidence_levels"] = {
        "A": _scenario_evidence(cmp["scenarios"]["A"], has_rag=False),
        "B": _scenario_evidence(cmp["scenarios"]["B"], has_rag=False),
    }
    validated_predictions = {
        "A": _validated_prediction(cmp["scenarios"]["A"]["kind"], cmp["profile"]),
        "B": _validated_prediction(cmp["scenarios"]["B"]["kind"], cmp["profile"]),
    }
    cmp["validated_predictions"] = validated_predictions
    indicator_evidence = {
        "A": indicators_mod.evidence_statuses(cmp["scenarios"]["A"]["kind"], validated_predictions["A"], scenario=cmp["scenarios"]["A"]),
        "B": indicators_mod.evidence_statuses(cmp["scenarios"]["B"]["kind"], validated_predictions["B"], scenario=cmp["scenarios"]["B"]),
    }
    koweps = koweps_evidence_for_request(req.model_dump())
    if koweps.get("available"):
        for side in ("A", "B"):
            indicator_evidence[side].update(koweps_indicator_statuses(koweps, side))
    cmp["koweps_evidence"] = koweps
    cmp["indicator_evidence"] = indicator_evidence
    return cmp


@app.post("/simulate")
def simulate(req: SimulateRequest) -> dict:
    """전체 파이프라인: (일기신호) → 엔진 L1~L5 수치 → 3지표 산출 →
    심리카드(민주 psych RAG) + 통계근거 → Claude 서사.

    - diary/emotions 로 안전 분기(위기 시 상담 안내). 엔진 수치는 항상 계산.
    - indicator_scores 는 엔진에서 산출(요청에 주면 override).
    - ANTHROPIC_API_KEY 없으면 수치·지표·근거는 반환하고 서사만 건너뛴다.
    """
    # 0) 일기모듈 — 감정신호 추출 & 해석 개인화
    # 일기 한 편의 정서를 만족도 입력값으로 변환해 예측 수치를 바꾸면 현재 감정과
    # 미래 결과가 순환 정의된다. 일기는 안전 분기·관심 축·서사에만 사용하고,
    # 수치 모델에는 사용자가 명시적으로 입력한 현재 상태만 전달한다.
    diary: dict = {"available": False}
    if getattr(req, "diary", None):
        diary = diary_bridge.analyze_diary(req.diary)

    # 0-1) 안전 분기(민주 safety, 정본) — 감정 + 일기 텍스트 종합
    safety_level, safety_hits = rag_safety.assess_safety(
        emotions=req.emotions, text=req.diary or ""
    )
    crisis = diary.get("block_report") or safety_level == "crisis"
    if crisis:
        cmp = build_comparison(req).model_dump()
        return {
            "profile": cmp["profile"],
            "choice_a": cmp["choice_a"],
            "choice_b": cmp["choice_b"],
            "compare": cmp,
            "diary": diary,
            "crisis": True,
            "safety_level": "crisis",
            "narrative": {"a": "", "b": "", "comparison": rag_safety.crisis_message(), "_crisis": True},
            "api_used": False,
            "model": settings.claude_model,
        }

    try:
        cmp = build_comparison(req).model_dump()
    except FileNotFoundError:
        return _simulate_without_artifacts(req, diary, safety_level)
    except Exception:
        # 아티팩트는 있는데 입력 데이터 스키마가 어긋난 경우(예: 패널 컬럼 누락).
        # 500 으로 죽이면 프론트가 원인을 알 수 없으므로 서사 폴백으로 내려가되,
        # 조용히 넘어가지 않도록 서버 로그에는 전체 스택을 남긴다.
        log.error("build_comparison 실패 — 서사 폴백으로 전환\n%s", traceback.format_exc())
        return _simulate_without_artifacts(req, diary, safety_level)
    scen_a = cmp["scenarios"]["A"]
    scen_b = cmp["scenarios"]["B"]
    baseline = getattr(req.profile, "monthly_wage", None)

    # 1) 3지표 산출(엔진 → 0~1). 요청 override 가 있으면 그걸 사용.
    #    나이를 넘기는 건 백분위를 **같은 나이대 안에서** 재기 위해서다
    #    ("29살 320만원" 이 잘 버는 건지는 나이대 없이 판정할 수 없다).
    age = getattr(req.profile, "age", None)
    det_a = indicators_mod.compute_indicators_detail(scen_a, baseline, age)
    det_b = indicators_mod.compute_indicators_detail(scen_b, baseline, age)
    ind_a = req.indicator_scores or det_a["scores"]
    ind_b = req.indicator_scores or det_b["scores"]
    validated_a = _validated_prediction(scen_a["kind"], cmp["profile"])
    validated_b = _validated_prediction(scen_b["kind"], cmp["profile"])
    status_a = indicators_mod.evidence_statuses(scen_a["kind"], validated_a, req.indicator_scores, scen_a)
    status_b = indicators_mod.evidence_statuses(scen_b["kind"], validated_b, req.indicator_scores, scen_b)
    koweps = koweps_evidence_for_request(req.model_dump())
    if koweps.get("available") and not req.indicator_scores:
        for side, statuses in (("A", status_a), ("B", status_b)):
            statuses.update(koweps_indicator_statuses(koweps, side))
        cmp["koweps_evidence"] = koweps
        cmp["indicator_evidence"] = {"A": status_a, "B": status_b}

    # 1-1) 성향 개인화(Option A): 가치가중치 → 서술순서·초점·질적강조·확신도.
    #      모델 매칭엔 관여 안 함. value_weights 없으면 focus_* = None(기존 동작 유지).
    #  · value_weights 직접 오면 그걸, 아니면 온보딩 순위(value_ranking)를
    #    지윤 정본(qmode.value_ranking.axis_weights)으로 변환해 사용.
    value_weights = getattr(req.profile, "value_weights", None)
    if not value_weights and getattr(req, "value_ranking", None):
        try:
            from qmode.value_ranking import axis_weights
            value_weights = axis_weights(req.value_ranking)
        except Exception:
            value_weights = None
    pz = personalize.build_personalization(
        value_weights=value_weights,
        diary_weights=req.diary_axis_weights,
        n_answers=req.diary_n_answers,
        indicator_scores_a=ind_a, indicator_scores_b=ind_b,
        disposition_block=req.disposition_block or "",
        mbti=req.profile.mbti,
    )
    focus_a = pz["focus_a"][0] if pz["focus_a"] else None
    focus_b = pz["focus_b"][0] if pz["focus_b"] else None

    # 2) 심리카드(민주 psych RAG): 3지표 + 감정 → 초점지표의 이론카드
    #    성향이 있으면 '중요하며 위태로운' 축을 초점으로 넘김(없으면 최저지표 폴백).
    #    ⚠ 초점은 '가장 낮은 지표' 로 정해지므로, 근거가 없어 중립값(0.5)만 채워진
    #    지표가 섞이면 자리채우기가 카드 선택을 좌우한다 → 측정된 지표만 넘긴다.
    #    (표시용 ind_a/ind_b 는 3개를 그대로 유지한다.)
    psych_a = get_psych_evidence(_measured(ind_a, det_a, req.indicator_scores),
                                 emotions=req.emotions,
                                 decision_type=req.choice_a, focus_override=focus_a)
    psych_b = get_psych_evidence(_measured(ind_b, det_b, req.indicator_scores),
                                 emotions=req.emotions,
                                 decision_type=req.choice_b, focus_override=focus_b)

    # 3) 통계 근거(숫자 근거) — 선택지별
    ev_a = stat_evidence.evidence_for_choice(req.choice_a)
    ev_b = stat_evidence.evidence_for_choice(req.choice_b)

    # 4) 서사 컨텍스트(note): 일기신호 + 심리카드 근거블록(A/B)
    note = cmp.get("note", "")
    note += (
        f"\n[미래 비교 기준 시점] 지금으로부터 정확히 {req.future_years}년 뒤. "
        "A와 B의 summary·future·gain·cost 및 이미지 장면 지시를 이 시점에 맞추고, "
        "다른 연도를 핵심 결과처럼 섞지 말 것. 장기 시점은 확정적으로 단정하지 말 것."
    )
    if req.choice_a_detail:
        note += f"\n[사용자가 적은 A의 구체적 상황] {req.choice_a_detail}"
    if req.choice_b_detail:
        note += f"\n[사용자가 적은 B의 구체적 상황] {req.choice_b_detail}"
    if req.choice_a_context:
        note += "\n[A 구조화 사건·추가 조건] " + json.dumps(req.choice_a_context, ensure_ascii=False)
    if req.choice_b_context:
        note += "\n[B 구조화 사건·추가 조건] " + json.dumps(req.choice_b_context, ensure_ascii=False)
    # 삶의 영역(domain) 컨텍스트 — '행동+영역' 구조화 입력의 영역 축을 서사에 알린다.
    _dl = _domain_labels(req.choice_a_domains) + _domain_labels(req.choice_b_domains)
    if _dl:
        note += "\n[관련 삶의 영역] " + " · ".join(dict.fromkeys(_dl))
    dctx = diary_bridge.diary_context_line(diary)
    if dctx:
        note += "  /  [일기 신호] " + dctx
    blk_a = build_psych_prompt_block(psych_a)
    blk_b = build_psych_prompt_block(psych_b)
    if blk_a:
        note += f"\n\n[A={req.choice_a} 심리근거]\n" + blk_a[:900]
    if blk_b:
        note += f"\n\n[B={req.choice_b} 심리근거]\n" + blk_b[:900]
    # 4-1) 성향 개인화 지시문(서술 우선순위·톤·질적강조) 주입 — 지윤 handoff §2.
    #      성향(가중치)이 실제로 있을 때만 붙인다.
    if value_weights:
        note = (note + "\n\n" + personalize.narrative_directive(
            pz, req.choice_a, req.choice_b)).strip()
    elif pz.get("disposition_block"):
        # 가치 순위를 건너뛰어도 MBTI·서술형 성향 재료는 서사에 전달한다.
        # 수치와 유사집단 매칭에는 쓰지 않고 표현 방식·주의점에만 사용한다.
        note = (note + "\n\n" + pz["disposition_block"] +
                "\n위 성향은 고정 성격이나 예측 피처로 단정하지 말고 설명의 톤과 관점에만 반영할 것.").strip()

    note = note.strip()

    # 접속 폭주 가드 — 하루 상한을 넘으면 **서사만** 생략한다(usage_guard 참조).
    # 수치·그래프·근거는 이미 계산이 끝났으므로 그대로 내려보낸다. 전시에서
    # 가장 아까운 건 아무것도 안 뜨는 화면이고, 비싼 건 Claude 호출 쪽이다.
    if not usage_guard.take():
        log.warning("일일 서사 한도 초과 — 서사 생략, 수치는 그대로 반환")
        narrative = {"a": "", "b": "", "comparison": "", "_busy": True}
    else:
        try:
            narrative = generate_scenarios(
                req.profile.model_dump(), scen_a, scen_b, ev_a, ev_b,
                note=note, model=settings.claude_model,
            )
        except Exception as exc:  # 키/ API 오류에도 수치·지표·근거는 반환
            narrative = {"a": f"(서사 생성 실패: {type(exc).__name__})", "b": "", "comparison": "", "_error": str(exc)[:300]}

    # 영역별 데이터 라우팅(항목3) — 각 선택의 삶의 영역 → 실측 집단통계 지표
    routed_a = route_domains(req.choice_a_domains, {
        **cmp["profile"], "choice": req.choice_a_detail or req.choice_a,
    })
    routed_b = route_domains(req.choice_b_domains, {
        **cmp["profile"], "choice": req.choice_b_detail or req.choice_b,
    })

    return {
        "profile": cmp["profile"],
        "choice_a": cmp["choice_a"],
        "choice_b": cmp["choice_b"],
        "snapshots": cmp.get("snapshots"),
        "compare": cmp,
        "indicators": {"A": ind_a, "B": ind_b},
        "indicators_measured": True,
        # 3지표의 근거 — 각 구성요소가 같은 나이대에서 몇 백분위인지. 점수만 보면
        # 어느 항이 지표를 끌어내렸는지 알 수 없어 해석·검증이 불가능하다.
        "indicator_detail": {
            "A": {k: v for k, v in det_a.items() if k != "scores"},
            "B": {k: v for k, v in det_b.items() if k != "scores"},
        },
        "indicator_evidence": {"A": status_a, "B": status_b},
        "validated_predictions": {"A": validated_a, "B": validated_b},
        "koweps_evidence": koweps,
        "personalization": pz,
        "prediction_contract": {
            "mode": "profile_matched_prediction",
            "numeric_inputs": "나이·성별·학력·소득·직종·고용상태 등 명시적 현재 조건",
            "diary_role": "안전 감지·관심 지표 우선순위·심리 해석·서사만 조정하며 예측 수치는 변경하지 않음",
            "score_definition": "0~1 지표는 동일 연령 또는 유사 조건 분포에서의 백분위 위치이며 성공확률이나 종합 우열 점수가 아님",
            "missing_policy": "직접 결과변수가 없으면 대리지표 또는 근거 부족으로 표시하고 임의 점수를 생성하지 않음",
        },
        "psych": {
            "A": {"focus": psych_a.get("focus_indicator"), "level": psych_a.get("level"),
                  "cards": [c["card_id"] for c in psych_a.get("cards", [])]},
            "B": {"focus": psych_b.get("focus_indicator"), "level": psych_b.get("level"),
                  "cards": [c["card_id"] for c in psych_b.get("cards", [])]},
        },
        "evidence": {"A": ev_a, "B": ev_b},
        # 근거 수준(항목4): 시나리오별 4단계 라벨 + domain 그래프 가드
        "evidence_levels": {
            "A": _scenario_evidence(cmp["scenarios"]["A"], bool(psych_a.get("cards"))),
            "B": _scenario_evidence(cmp["scenarios"]["B"], bool(psych_b.get("cards"))),
        },
        # 영역별 데이터 라우팅(항목3): 각 선택의 삶의 영역 → 실측 집단통계 지표
        "domain_stats": {"A": routed_a, "B": routed_b},
        "domain_coverage": {
            "A": _coverage_from_routes(routed_a),
            "B": _coverage_from_routes(routed_b),
        },
        "diary": diary,
        "safety_level": safety_level,
        "support_note": diary_bridge.crisis_message(diary["crisis_level"])
        if diary.get("crisis_level", 0) >= 2 else "",
        "narrative": narrative,
        "api_used": not narrative.get("_skipped", False),
        "model": settings.claude_model,
    }


@app.post("/avatar/from-photo", response_model=AvatarFromPhotoResponse)
def avatar_from_photo(req: AvatarFromPhotoRequest) -> AvatarFromPhotoResponse:
    """셀카 한 장 → 아바타 설정. 사진은 디스크에 쓰지 않고 응답 후 버린다."""
    try:
        return AvatarFromPhotoResponse(**avatar_vision.analyze(req.image, req.options))
    except avatar_vision.AvatarVisionError as e:
        raise HTTPException(status_code=400, detail=str(e))
