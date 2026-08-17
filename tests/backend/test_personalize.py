import personalize as P

def approx(a, b, e=1e-3): return abs(a - b) < e

vw = {"경제": 0.20, "관계": 0.15, "성장": 0.35, "자기실현": 0.15, "안정": 0.15}

# 1) 5축 → 지표 가중치. v3 부터 AXIS_TO_INDICATOR 가 항등이라 축 가중치가 그대로 간다.
#    예전엔 관계·자기실현·안정 3축이 '삶의질' 하나로 접혀서, 사용자가 축을 어떻게
#    정렬하든 그 셋은 한 칸으로 뭉개졌다(합산이면 0.45로 과대대표, 평균이면 0.15).
#    이제 접히지 않으므로 축별 답이 그대로 남는다.
iw = P.indicator_weights(vw)
print("indicator_weights(항등):", iw)
for ax in vw:
    assert approx(iw[ax], vw[ax]), (ax, iw[ax], vw[ax])
assert approx(sum(iw.values()), 1.0)

# 1-R) ★회귀: 관계·자기실현·안정이 더는 한 칸으로 합쳐지지 않는다.
assert len({"관계", "자기실현", "안정"} & set(iw)) == 3

# 2) 서술 우선순위: 성장 > 경제 > (관계·자기실현·안정 동점 → INDICATORS 고정순)
print("priority_order:", P.priority_order(vw))
assert P.priority_order(vw)[:2] == ["성장", "경제"]

# 2-R) ★회귀: 성장 1순위(실제 axis_weights 예시)면 narrate_order 맨 앞이 성장이어야 함
vw_growth_top = {"경제": 0.16, "관계": 0.14, "성장": 0.32, "자기실현": 0.14, "안정": 0.24}
print("growth-top narrate_order:", P.priority_order(vw_growth_top))
assert P.priority_order(vw_growth_top)[0] == "성장"
# 2순위는 안정(0.24) — 예전엔 관계+자기실현+안정이 뭉쳐 순위가 왜곡됐다.
assert P.priority_order(vw_growth_top)[1] == "안정"

# 3) 확신도 / recency (변경 없음)
assert P.confidence(0)["diary_weight"] == 0.0
assert P.confidence(30)["level"] == "높음"

# 4) blend (value_weights 직접 사용)
assert P.blend_weights(vw, None, P.confidence(30)) == vw
dw = {"경제": 0.5, "관계": 0.1, "성장": 0.1, "자기실현": 0.2, "안정": 0.1}
blended = P.blend_weights(vw, dw, P.confidence(30))
assert approx(sum(blended.values()), 1.0)

# 5) 심리카드 초점 — 5축 점수
scores = {"경제": 0.62, "성장": 0.40, "관계": 0.55, "자기실현": 0.50, "안정": 0.18}
assert P.psych_focus(scores, None) == ("안정", 0.18)          # value 없으면 최저축
assert P.psych_focus(scores, vw, mode="value")[0] == "성장"   # 가치 1순위 축
f, s = P.psych_focus(scores, vw, mode="need_x_value")
print("psych_focus need_x_value:", f, s)
assert f == "성장"

# 6) 질적 A/B 강조 — 우선순위대로, 종합 점수 없음
ind_a = {"경제": 0.70, "성장": 0.55, "관계": 0.40, "자기실현": 0.50, "안정": 0.30}
ind_b = {"경제": 0.50, "성장": 0.35, "관계": 0.62, "자기실현": 0.50, "안정": 0.62}
emp = P.emphasis_compare(ind_a, ind_b, vw)
print("emphasis[0]:", emp[0])
assert emp[0]["indicator"] == "성장" and emp[0]["verdict"] == "A가 높음"

# 7) 진입점
res = P.build_personalization(value_weights=vw, n_answers=3,
                              indicator_scores_a=ind_a, indicator_scores_b=ind_b)
print("focus_a:", res["focus_a"], "narrate_order:", res["narrate_order"])
assert res["focus_a"][0] == "성장"
assert res["narrate_order"][0] == "성장"

# 8) MBTI는 구조화된 서사 스타일 prior로만 반영되고 수치 가중치는 바꾸지 않는다.
mbti_res = P.build_personalization(value_weights=vw, mbti="INTJ")
assert mbti_res["mbti_prior_applied"] is True
assert "근거와 장단점을 구조적으로 제시" in mbti_res["disposition_block"]
assert "불확실성과 안전장치를 먼저 설명" in mbti_res["disposition_block"]
assert mbti_res["effective_weights"] == vw
assert P.mbti_narrative_directive("XXXX") == ""

print("\nALL PASSED (5축 항등 매핑) ✅")
