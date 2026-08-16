# qmode → 예측 서사 연결 인수인계

질문형 일기(qmode)가 뽑아낸 **성향·취향·언어신호**를, 예측(평행우주 시나리오) 서사에
반영하기 위한 연결 명세. **backend 원본은 수정하지 말 것** — qmode가 주는 '재료'를
예측 서사 프롬프트에 주입만 하면 된다(재료 제공형).

---

## 0. 한 줄 요약

qmode는 세 덩어리의 **재료(텍스트 블록 + 수치)** 를 준다.
예측 서사 생성 프롬프트에 **그대로 끼워 넣으면** 개인화된 시나리오가 나온다.
예측 **모델(KNN·EconML·lifelines)의 피처로는 넣지 않는다**(학습 피처 고정).

---

## 1. qmode가 주는 재료 (호출법)

모두 `diary_module/qmode/` 안. `sessions`는 `session.analyze_session()` 결과 리스트
(보통 1주일치). `diary_metrics`는 아래 ①에서 나온다.

```python
import sys; sys.path.insert(0, "diary_module")
from qmode.session import build_diary_metrics
from qmode import disposition, interests, value_ranking

# ① 언어신호 누적 (답변만 반영, 길이게이트·부러움 분기 적용)
agg = build_diary_metrics(sessions)
#   agg["diary_metrics"]  → {emotion_valence, coping_balance, insight_ratio, ...} 또는 None(<5답변)
#   agg["per_question"]   → 질문별 평균 신호
#   agg["envy"]           → 부러움 판정(benign만 가치축 신호)

# ② 온보딩 가치순위 → 5축 가중치 (유저가 매긴 순위 리스트)
vw = value_ranking.axis_weights(ranked_card_ids)   # {"경제":0.30, "관계":0.30, ...} 합=1

# ③ 성향(가치+전달스타일) 통합 블록
disp = disposition.analyze_disposition(sessions, agg["diary_metrics"], value_weights=vw)
#   disp["block"]           → 프롬프트에 넣을 텍스트(내용 강조순서 + 전달스타일)
#   disp["delivery_style"]  → {flags, guide}  (톤 조절용)

# ④ 취향·관심사(라포)
interest_block = interests.build_block(interests.collect(sessions))   # 텍스트(없으면 "")
```

---

## 2. 예측 서사 프롬프트에 넣는 법

예측 서사를 만드는 Claude 프롬프트(backend/utils/claude_api.py의 서사 생성부)에
**아래 두 블록을 컨텍스트로 추가**하면 된다. 형식은 이미 사람이 읽는 지시문이라 가공 불필요.

```
[예측 결과 요약 … 기존 그대로 …]

{disp["block"]}          # ← 내용 강조 순서 + 전달 스타일
{interest_block}         # ← 취향(라포·비유 재료)

지시: 위 '서술 우선순위'가 높은 축부터 시나리오를 서술하고,
      '전달 스타일'에 맞춰 톤을 잡아라. 취향은 자연스러울 때만 비유로.
      단정하지 말 것(성향은 초기값이며 갱신됨).
```

**효과**: 관계·안정 1순위 유저 → 관계·안정 결과부터 서술 / 회피경향 유저 →
"작은 한 걸음"으로 제안 / 클라이밍 좋아하면 "한 홀드씩 잡듯" 같은 비유.

---

## 3. 가치 축 → 예측 지표 매핑

`value_ranking.AXIS_TO_INDICATOR`:

| 가치 축 | 예측 지표 |
|---|---|
| 경제 | 경제적안정도 |
| 성장 | 성장가능성 |
| 관계 / 자기실현 / 안정 | 삶의질(프록시) |

→ "이 유저는 경제 1순위" 면 예측의 **경제적안정도·소득 궤적을 먼저·비중 있게** 서술.

---

## 4. ⚠️ confidence / recency (아직 미구현 — 예측 쪽에서 함께 설계 요망)

지금 재료엔 **"얼마나 쌓였는지"** 가중치가 없다. 예측에서 얕은 데이터로 확신하면 안 되므로:

- `agg["n_answers"]` 적으면(예: <10) → 서사를 **"아직 단정 어렵지만…"** 톤으로.
- 가치순위는 **온보딩 초기값** → 일기 쌓일수록 언어지표로 갱신. 데이터 적으면 순위 위주,
  많으면 일기신호 위주로 무게 이동.
- 오래된 신호는 **감쇠(recency)** 권장(최근 주가 더 무겁게).

이 층은 예측 파이프라인에서 `n_answers`·기간을 보고 톤/가중치를 조절하는 게 자연스럽다.

---

## 5. 절대 하지 말 것

- ❌ 예측 **모델(KNN/EconML/lifelines)의 입력 피처**로 넣기 → 학습 피처 고정. 재학습 필요.
      성향·취향·건강은 **서사·톤에만** 반영.
- ❌ **진단 라벨**("우울장애입니다") / **또래 % 수치**를 유저 서사 본문에.
- ❌ 성향을 **고정 특성**으로 단정. 항상 "초기값·갱신됨" 전제.
- ❌ `backend/` 원본 수정. qmode 재료를 주입만.

---

## 6. 참고 — 조립 예시가 이미 있음

`diary_module/qmode/report.py`의 `build_narrative_prompt()`가 위 재료들을 실제로
조립해 Claude 서사를 만드는 **동작하는 예시**다. 예측 서사도 같은 방식으로 조립하면 된다.
샘플 출력: `diary_module/qmode/samples/sample_report.txt`.

---

## 7. suin 예측 서사 연결 — 실제 인터페이스 기준 (2026-07-31 갱신)

성향 추출이 **사전지표 → 구조화 LLM**으로 바뀌었고, 이직 서사용 재료가 생겼다.
suin `backend/utils/claude_api.py`의 현재 `generate_narrative`는 성향을 **아직 안 받는다**
(수치 4개만). 아래 **최소 추가**로 우리 재료를 끼우면 된다. suin이 추가한
`PredictRequest`의 상태필드(monthly_wage·satis_overall 등)는 **KNN 매칭용 상태 수치**라
우리 성향(가치·대처)과 **다른 것 — 그대로 두면 된다**(성향은 모델 피처로 넣지 않는다, §5).

### (a) qmode가 재료 만드는 법 (우리 쪽, 주간 배치)
```python
from qmode import disposition, disposition_llm, value_ranking
from qmode.session import build_diary_metrics

agg = build_diary_metrics(sessions)                         # 누적(길이게이트·부러움)
vw  = value_ranking.axis_weights(ranked_card_ids)           # 온보딩 순위 → 5축(prior)
extract, err = disposition_llm.extract(sessions)            # LLM 구조화 추출(대처·이직렌즈)
blended = disposition_llm.blend_weights(vw, extract,        # 갱신(가치는 온보딩 주도, α≤0.3)
                                        n_answers=agg["n_answers"])
persona_block = disposition.build_jobchange_material(       # ← suin에 넘길 '재료' 문자열
    blended["weights"], extract, decided_by=blended["note"])
```
`extract`/키 없으면 `build_jobchange_material(vw, None)` 로도 동작(온보딩만으로 프레임).

### (b) suin backend 배선 — 3곳 소편집 (backend는 stateless라 persona_block이 요청에 실려 옴)

backend `PredictRequest`엔 user_id·일기가 없다(순수 예측 API). 그래서 우리 모델을
backend가 돌리지 않고, **우리가 만든 persona_block 문자열을 요청에 실어 보내** 통과시킨다.
persona_block 없으면 기존과 100% 동일(하위호환). main.py의 try/except가 이미 방어.

**① `backend/schemas.py` PredictRequest — 필드 1줄 (edu_level 아래):**
```python
    persona_block: Optional[str] = None   # qmode 성향 재료(이직 서사 개인화). 없으면 기존과 동일
```
**② `backend/main.py`(현재 91행) — 호출에 인자 1개:**
```python
    narrative = generate_narrative(req, expected_wage or 0, effect or 0, survival or 0,
                                   persona_block=req.persona_block)
```
**③ `backend/utils/claude_api.py` generate_narrative — 파라미터 + 프롬프트 3줄:**
```python
def generate_narrative(req, expected_wage, causal_effect, survival_months,
                       persona_block=None):          # ← 추가
    ...
    if persona_block:                                # ← 추가
        prompt += (f"\n\n{persona_block}\n"
                   "지시: 위 '지표 강조 순서'가 높은 것부터 서술하고, '리스크 프레임'과 "
                   "'전달 스타일'에 맞춰 톤을 잡아라. 수치는 절대 바꾸지 말고, 불리한 축도 "
                   "숨기지 마라(순서·톤만 조정).")
    resp = _get_client().messages.create(...)
```

### (b-2) persona_block은 누가 만드나 (우리쪽, 주 1회 배치)
```python
from qmode.disposition_model import DispositionModel
prof = DispositionModel().analyze(ranked_cards, sessions)   # 온보딩 + 그 주 일기
persona_block = prof["jobchange_material"]                  # → 유저 프로필 DB 저장
# 예측 요청 시 프론트가 저장된 persona_block을 PredictRequest에 실어 POST
```
데이터 흐름: `[주1회] DispositionModel→persona_block 저장 → [예측요청] 프론트가 요청에 실음
→ [backend] req.persona_block→generate_narrative`.  수치는 모델 그대로, 서사 순서·톤만.

### (c) persona_block 예시 (P1 안정·회피형)
```
[이직 서사용 성향 재료 — 서술 방식에만 반영, 예측 수치는 불변. 갱신근거: α=0.30 …]
· 지표 강조 순서: 삶의질 → 성장가능성 → 경제적안정도
· 리스크 프레임: '위협' 아닌 '관리·재구성'으로 먼저, 작은 첫 스텝으로 분해.
· 결정 방식(mixed): 핵심 수치 한둘 + 그 의미를 함께.
· 전달 스타일: 정서부하 높음; 자기초점 강함
· 이 사람이 가장 지키려는 것: 예측 가능하고 안정적인 일상 …
· 가드: 불리한 축도 숨기지 말 것. 성향은 초기값이며 갱신됨 — 단정 금지.
```
→ **같은 수치라도** P1(삶의질부터·관리톤) vs 경제형(경제부터) 서사가 갈린다.
검증: `python diary_module/qmode/dataset/build.py P1_stability --llm`.
