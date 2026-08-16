# 개인 성향 파악 모델 (DispositionModel) — 모델 카드

온보딩 가치순위 + 질문형 일기 → **성향 프로파일 + 이직 서사용 재료**를 돌려주는
단일 진입점. 파일: `diary_module/qmode/disposition_model.py`.

## 1. 한 줄 요약
가치관은 **온보딩 강제순위**(검증된 신호), 사고·대처·이직성향은 **LLM 구조화 추출**,
둘을 **갱신 블렌딩**해 성향을 만든다. 서사는 만들지 않고 **재료만** 준다(suin 관할 존중).

## 2. 호출법 (한 번)
```python
from qmode.disposition_model import DispositionModel

m = DispositionModel()                      # 엔진: claude-sonnet-5
prof = m.analyze(
    ranked_cards,      # 온보딩 가치순위(카드 id 리스트). None이면 균등 prior
    sessions,          # session.analyze_session 결과들(items[].answer/metrics)
    mbti="INTJ",       # (선택) 스타일 prior — 결정·위험·톤의 초기값. 일기가 갱신(일기>MBTI)
    use_llm=True,      # False = 오프라인 폴백(온보딩·지표만, 대처/이직렌즈 없음)
    robust=False,      # True = 추출 2회 교차확인 → 불일치 시 confidence 강등
)

# 팀원 personalize.py(A/B·심리초점·wiring)에 넘길 때:
pz_in = DispositionModel.to_personalize_inputs(prof)   # {value_weights, diary_weights:None, n_answers, disposition_block}
# → personalize.build_personalization(**pz_in) 로 소비. personalize.py 무변경.
```

**MBTI(스타일 prior)**: 가치가 '온보딩 순위(prior)→일기(갱신)'인 것과 같은 패턴을 스타일엔 MBTI로.
T/F→결정방식, J/P→위험감수, E/I·S/N→전달 톤. **일기 LLM이 있으면 결정·위험은 LLM이 이기고**
(MBTI 신뢰도 보정), MBTI 톤만 얹힌다. 콜드스타트(일기 없음)엔 MBTI가 스타일을 채운다. `mbti.py`.

**personalize.py 화해**: 팀원이 이미 만든 소비자(A/B 비교·심리카드 초점·main.py 연결)는
그대로 두고, 그 `diary_weights`(옛 metrics, 신뢰성 실패) 대신 이 모델의 LLM 출력을
`to_personalize_inputs()`로 주입한다(value 재블렌딩 방지 위해 diary_weights=None).

## 3. 출력 (prof)
| 키 | 뜻 |
|---|---|
| `value_weights` / `value_order` | 갱신된 5축 가중치 · 서술 우선순위 |
| `coping` | 대처: approach / avoidant / mixed |
| `risk_tolerance` | 이직 위험감수도 0~1 |
| `decision_style` | 결정 방식: analytic / intuitive / mixed |
| `protect_most` | 이 사람이 가장 지키려는 것 |
| `delivery` | 전달 스타일 가이드 |
| `summary` | 한 줄 성향 요약 |
| `confidence` | `{score, level(높음/보통/낮음), note}` — 얼마나 믿을지 |
| `consistency_ok` | robust=True일 때 재현 일치 여부 |
| `envy` | 부러움 판정(benign만 가치축 신호) |
| **`jobchange_material`** | **suin 예측서사에 끼울 재료 블록** |
| `raw_extract` | LLM 원 추출(디버그·로컬모델 학습라벨용) |

## 4. 신뢰성 (실측)
- **일관성**: 같은 일기 두 번 추출 → 핵심 3차원(대처·위험감수도·결정방식) **100% 재현**,
  전체 93%. 흔들리는 가치축은 온보딩이 잡아줌(α≤0.3). (`dataset/verify.py`)
- **confidence**: 데이터량(≈40답변=충분) × 추출확신, robust 불일치 시 ×0.7.
- **견고성**: 529/5xx/rate 전이오류에 백오프 재시도. 키 없으면 use_llm=False로 폴백.
- **안전**: 위기·길이·부러움 게이트는 LLM 밖 결정적 코드가 담당(세션 단계).

## 5. 한계 (정직하게)
- **합성 데이터 검증** — 5인 페르소나(수기 작성) 기준. **실사용자 정확도는 별개.**
- **API 의존** — 정확성 위해 LLM 사용. 프라이버시·비용·오프라인이 중요해지면 §6.
- **지표 순서 granularity** — backend 지표 3개(경제/성장/삶의질). 관계·자율·안정은
  '삶의질'로 뭉치므로 `삶의질 세부 초점` 하위힌트로 구분(backend 세분화 전 stopgap).

## 6. 로컬 모델 증류 (후속 — API 뗄 때)
`raw_extract`가 그대로 **학습 라벨**이 된다:
```
LLM(교사)로 대량 일기 라벨링  →  로컬 인코더(roberta류) 파인튜닝  →  API 뗌
```
가치축은 온보딩이라 모델 불필요 — **대처·위험감수도·결정방식만** 회귀/분류로 학습하면 됨.
일관성 93%가 "좋은 교사" 근거. 정확도는 LLM보다 낮되 무료·온디바이스·프라이빗.

## 7. 예측 서사 연결
`prof["jobchange_material"]`을 suin `generate_narrative(persona_block=...)`에 전달.
상세: `PREDICTION_HANDOFF.md` §7.

## 8. 데모
```bash
python diary_module/qmode/disposition_model.py P1_stability --robust   # 단일 성향
python diary_module/qmode/dataset/demo.py --llm                        # 5인 이직 분기
python diary_module/qmode/dataset/verify.py                            # 일관성 검증
```
