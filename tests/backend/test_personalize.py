import personalize as P

def approx(a, b, e=1e-3): return abs(a - b) < e

vw = {"경제": 0.20, "관계": 0.15, "성장": 0.35, "자기실현": 0.15, "안정": 0.15}

# 1) 5축 → 3지표 [평균(mean) 집계]. 삶의질 = mean(관계,자기실현,안정)=0.15 (합산이면 0.45였음)
iw = P.indicator_weights(vw)
print("indicator_weights(mean):", iw)
# 정규화 전 비율: 경제0.20, 성장0.35, 삶의질0.15 → 합0.70
assert approx(iw["성장가능성"], 0.35 / 0.70)      # 0.5
assert approx(iw["경제적안정도"], 0.20 / 0.70)     # 0.2857
assert approx(iw["삶의질"], 0.15 / 0.70)          # 0.2143
assert approx(sum(iw.values()), 1.0)

# 2) 서술 우선순위: 성장 > 경제 > 삶의질  (합산 시절엔 삶의질이 맨 앞이었음)
print("priority_order:", P.priority_order(vw))
assert P.priority_order(vw) == ["성장가능성", "경제적안정도", "삶의질"]

# 2-R) ★회귀: 성장 1순위(실제 axis_weights 예시)면 narrate_order 맨 앞이 성장가능성이어야 함
vw_growth_top = {"경제": 0.16, "관계": 0.14, "성장": 0.32, "자기실현": 0.14, "안정": 0.24}
print("growth-top narrate_order:", P.priority_order(vw_growth_top))
assert P.priority_order(vw_growth_top)[0] == "성장가능성"   # 합산이면 삶의질이 앞섰음 → 수정 확인

# 3) 확신도 / recency (변경 없음)
assert P.confidence(0)["diary_weight"] == 0.0
assert P.confidence(30)["level"] == "높음"

# 4) blend (value_weights 직접 사용 — mean 변경과 무관)
assert P.blend_weights(vw, None, P.confidence(30)) == vw
dw = {"경제": 0.5, "관계": 0.1, "성장": 0.1, "자기실현": 0.2, "안정": 0.1}
blended = P.blend_weights(vw, dw, P.confidence(30))
assert approx(sum(blended.values()), 1.0)

# 5) 심리카드 초점
scores = {"경제적안정도": 0.62, "성장가능성": 0.40, "삶의질": 0.18}
assert P.psych_focus(scores, None) == ("삶의질", 0.18)             # value 없으면 최저지표
assert P.psych_focus(scores, vw, mode="value")[0] == "성장가능성"  # mean → 성장 최상위(합산이면 삶의질)
f, s = P.psych_focus(scores, vw, mode="need_x_value")
print("psych_focus need_x_value:", f, s)
assert f == "성장가능성"

# 6) 질적 A/B 강조 — 우선순위대로, 종합 점수 없음
ind_a = {"경제적안정도": 0.70, "성장가능성": 0.55, "삶의질": 0.30}
ind_b = {"경제적안정도": 0.50, "성장가능성": 0.35, "삶의질": 0.62}
emp = P.emphasis_compare(ind_a, ind_b, vw)
print("emphasis[0]:", emp[0])
assert emp[0]["indicator"] == "성장가능성" and emp[0]["verdict"] == "A가 높음"

# 7) 진입점
res = P.build_personalization(value_weights=vw, n_answers=3,
                              indicator_scores_a=ind_a, indicator_scores_b=ind_b)
print("focus_a:", res["focus_a"], "narrate_order:", res["narrate_order"])
assert res["focus_a"][0] == "성장가능성"
assert res["narrate_order"][0] == "성장가능성"

print("\nALL PASSED (mean 집계) ✅")
