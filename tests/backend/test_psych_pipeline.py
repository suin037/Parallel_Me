"""심리 RAG 파이프라인 무료 검증(모의) — 실제 Claude·모델 .pkl 없이 로직만 테스트.

실행:  cd backend && "$KPY" test_psych_pipeline.py
검증 대상: 검색 → 근거블록 → 프롬프트 주입(안전분기) → /predict 배선.
검증 안 함: Claude가 실제로 근거를 잘 지키는지(그건 라이브 호출 필요).
"""

from config import settings
from schemas import PredictRequest, NeighborCase
from utils.claude_api import build_prompt, generate_narrative
from rag.psych_narrative import get_psych_evidence, build_psych_prompt_block, select_focus
from rag.safety import assess_safety, crisis_message

PASS, FAIL = "✅ PASS", "❌ FAIL"
n_fail = 0


def check(name, cond):
    global n_fail
    print(f"{PASS if cond else FAIL}  {name}")
    if not cond:
        n_fail += 1


req = PredictRequest(age=29, sex="여성", major="경영", choice="이직",
                     indicator_scores={"경제적안정도": 0.62, "성장가능성": 0.40, "삶의질": 0.18},
                     emotions=["후회", "자책"])

# ── 1. 지표 초점 선택 ────────────────────────────────────────────────
focus, score = select_focus(req.indicator_scores)
check("select_focus → 가장 낮은 지표(삶의질) 선택", focus == "삶의질" and abs(score - 0.18) < 1e-9)
check("select_focus 언더스코어 표기 정규화", select_focus({"삶의_질": 0.1})[0] == "삶의질")
check("select_focus 빈 입력 → (None,None)", select_focus({}) == (None, None))

# ── 2. 검색 → 근거블록 ───────────────────────────────────────────────
ev = get_psych_evidence(req.indicator_scores, emotions=req.emotions, decision_type=req.choice)
check("evidence 초점=삶의질/level=낮음", ev["focus_indicator"] == "삶의질" and ev["level"] == "낮음")
check("evidence 카드 검색됨(>0)", len(ev["cards"]) > 0)
check("검색 카드 모두 지표일치", all(c["indicator_matched"] for c in ev["cards"]))
block = build_psych_prompt_block(ev)
check("근거블록에 '출처' 포함(인용 강제 재료)", "출처:" in block)
check("근거블록에 '행동제안 후보' 포함", "행동제안 후보" in block)
check("빈 evidence → 빈 블록", build_psych_prompt_block({"cards": []}) == "")

# ── 3. 프롬프트 안전분기(순수함수) ───────────────────────────────────
p_with = build_prompt(req, 3000000, 20000, 40.0, psych_block=block)
p_without = build_prompt(req, 3000000, 20000, 40.0, psych_block="")
check("psych_block 있으면 출처인용 지시 포함", "출처를 문장 안에 짧게 인용" in p_with)
check("psych_block 있으면 근거블록 본문 주입됨", "심리학 근거 카드" in p_with)
check("psych_block 없으면 기본 2~3문장 지시", "2~3문장" in p_without and "심리학 근거 카드" not in p_without)

# ── 4. generate_narrative mock 모드(무료) ────────────────────────────
settings.mock_llm = True
out_with = generate_narrative(req, 3000000, 20000, 40.0, psych_block=block)
out_without = generate_narrative(req, 3000000, 20000, 40.0, psych_block="")
check("mock: psych 있으면 '심리근거 주입됨' 태그", "심리근거 주입됨" in out_with)
check("mock: psych 없으면 '심리근거 없음' 태그", "심리근거 없음" in out_without)

# ── 4b. 위기 안전 분기 ───────────────────────────────────────────────
check("assess_safety: 급성 위기 감지", assess_safety(["불안", "죽고 싶다"])[0] == "crisis")
check("assess_safety: 강한 고통 감지", assess_safety(["무력감", "절망"])[0] == "high_distress")
check("assess_safety: 후회·자책은 normal(과잉차단 방지)", assess_safety(["후회", "자책"])[0] == "normal")
check("assess_safety: 빈 입력 normal", assess_safety([])[0] == "normal")
check("crisis_message에 상담 자원(109) 포함", "109" in crisis_message())
# high_distress 프롬프트: 행동제안 강요 금지 지시 포함
p_hd = build_prompt(req, 0, 0, 0.0, psych_block=block, safety_mode="high_distress")
check("high_distress 프롬프트: 행동제안 비강요 지시", "강요하지 말" in p_hd)
check("high_distress mock: safety 태그 반영", "safety=high_distress" in generate_narrative(req, 0, 0, 0.0, psych_block=block, safety_mode="high_distress"))

# ── 5. /predict 배선(모델·generate_narrative monkeypatch) ────────────
import main
main.find_neighbors = lambda features, k=5: [NeighborCase(similarity=1.0, monthly_wage=3000000, job_category="경영사무")]
main.estimate_effect = lambda features, choice: 20000.0
main.estimate_survival = lambda features: 40.0
captured = {}
def _spy(req, ew, ce, sm, psych_block="", safety_mode="normal"):
    captured["psych_block"] = psych_block
    captured["safety_mode"] = safety_mode
    return "narrative-stub"
main.generate_narrative = _spy

resp_with = main.predict(req)
check("/predict: 지표 있으면 psych_block 주입됨", captured["psych_block"] != "")

req_plain = PredictRequest(age=29, sex="여성", major="경영", choice="이직")  # 지표·감정 없음
resp_without = main.predict(req_plain)
check("/predict: 지표 없으면 psych_block 빈 문자열", captured["psych_block"] == "")
check("/predict: 응답 스키마 정상(narrative 채워짐)", resp_with.narrative == "narrative-stub")

# 급성 위기: generate_narrative 호출 없이 자원 메시지로 분기
captured["called"] = False
def _spy2(*a, **k):
    captured["called"] = True
    return "should-not-be-used"
main.generate_narrative = _spy2
req_crisis = PredictRequest(age=29, sex="여성", major="경영", choice="이직",
                            emotions=["무력감", "죽고 싶다"])
resp_crisis = main.predict(req_crisis)
check("/predict crisis: safety_level=crisis", resp_crisis.safety_level == "crisis")
check("/predict crisis: 서사 대신 상담 자원(109) 반환", "109" in resp_crisis.narrative)
check("/predict crisis: generate_narrative 미호출(하드 분기)", captured["called"] is False)

print("\n" + ("🎉 전부 통과" if n_fail == 0 else f"⚠️ 실패 {n_fail}건"))
raise SystemExit(1 if n_fail else 0)
