"""실제 Claude 호출로 심리 RAG 라이브 검증. (ANTHROPIC_API_KEY 필요, 1회 호출 소액 과금)

무료 목 테스트(test_psych_pipeline.py)가 파이프라인 '로직'을 검증한다면,
이 스크립트는 유일하게 남은 것 = "생성 문장이 근거·출처를 실제로 지키는지"를 확인한다.

실행:  cd backend && "$KPY" test_live_narrative.py
"""

from config import settings
from schemas import PredictRequest
from rag.psych_narrative import get_psych_evidence, build_psych_prompt_block
from rag.safety import assess_safety
from utils.claude_api import generate_narrative

if settings.mock_llm:
    raise SystemExit("⚠️ MOCK_LLM=true 상태. .env에서 MOCK_LLM 줄을 지우거나 false로 바꾸세요.")
if not settings.anthropic_api_key:
    raise SystemExit("⚠️ .env에 ANTHROPIC_API_KEY가 비어있습니다. 키를 넣어주세요.")

print(f"모델: {settings.claude_model}")
print("시나리오: 삶의질=0.18(낮음) · 감정=[후회,자책] · 이직 고민\n")

req = PredictRequest(
    age=29, sex="여성", major="경영", choice="이직",
    indicator_scores={"경제적안정도": 0.62, "성장가능성": 0.40, "삶의질": 0.18},
    emotions=["후회", "자책"],
)

# 1) 검색 → 근거 카드
ev = get_psych_evidence(req.indicator_scores, emotions=req.emotions, decision_type=req.choice)
block = build_psych_prompt_block(ev)
print("검색된 근거 카드:")
sources = []
for c in ev["cards"]:
    print(f"  · {c['card_id']}  (출처: {c['source'][:55]}…)")
    sources.append(c["source"])
print()

# 2) 안전 등급(정상이어야 함)
safety_level, _ = assess_safety(req.emotions)

# 3) 실제 Claude 호출
narrative = generate_narrative(
    req, expected_wage=3_000_000, causal_effect=20_000, survival_months=40.0,
    psych_block=block, safety_mode=safety_level,
)

print("=" * 60)
print("생성된 서사 (실제 Claude):")
print("=" * 60)
print(narrative)
print("=" * 60)

# 4) 근거 충실성 간이 검증: 검색된 이론의 저자/연도를 실제로 인용했는가
markers = ["Lazarus", "Folkman", "Fredrickson", "1984", "2004"]
cited = [m for m in markers if m in narrative]
print(f"\n출처 인용 확인: {'✅ 포함 — ' + ', '.join(cited) if cited else '⚠️ 인용 안 보임(프롬프트/카드 점검)'}")
print(f"안전 등급: {safety_level}")
