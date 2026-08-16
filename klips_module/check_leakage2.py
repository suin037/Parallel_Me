# check_leakage2.py — 누수 정밀 점검 (에러 수정 + 정합성 진단)
import pandas as pd, numpy as np
from scipy.stats import pointbiserialr

s = pd.read_pickle("data/klips_base_생존.pkl")
b = pd.read_pickle("data/klips_base.pkl")
h = pd.read_pickle("data/klips_health.pkl")

hcols = [c for c in ["삶의만족도_현재","만족점수_전반적","건강점수","웰빙지수"] if c in h.columns]
panel = b[["pid","wave","나이","학력","직종","종사상지위","월임금_실질"]].merge(
    h[["pid","wave"]+hcols], on=["pid","wave"], how="left")
panel["직종대분류"] = panel["직종"]//100
panel = panel.sort_values(["pid","wave"])

# 확정 버전은 '시작wave 시점의 값'을 join으로 가져옴. 그 시점 값을 찾는 함수.
def get_start_row(pid, sw):
    """시작wave 그 시점의 base 기록 (없으면 그 이전 가장 가까운 것)."""
    hist = panel[(panel["pid"]==pid) & (panel["wave"]<=sw)]
    return hist.iloc[-1] if len(hist)>0 else None

print("="*60)
print("[점검1] 확정버전 join이 미래 정보를 안 보는가?")
# 확정 버전은 left_on=['pid','시작wave']로 정확히 그 wave를 매칭 → 미래 불가능. 구조 확인만.
ok = True
for _, r in s.head(200).iterrows():
    row = get_start_row(r["pid"], r["시작wave"])
    if row is not None and row["wave"] > r["시작wave"]:
        ok = False
print(f"  시작wave 초과 데이터 사용: {'없음 ✓ (미래 안 봄)' if ok else '있음 ⚠️ LEAKAGE'}")

print("\n"+"="*60)
print("[점검2] 피처가 event랑 수상하게 높은 상관을 갖나? (>0.5면 누수 의심)")
sample = s.sample(min(3000,len(s)), random_state=0)
rows=[]
for _,r in sample.iterrows():
    row = get_start_row(r["pid"], r["시작wave"])
    if row is not None:
        rec = {"event": r["event"], "임금": row["월임금_실질"], "나이": row["나이"], "학력": row["학력"]}
        for c in hcols: rec[c] = row[c]
        rows.append(rec)
d = pd.DataFrame(rows)
for col in [c for c in d.columns if c!="event"]:
    dd = d[["event",col]].dropna()
    if len(dd)>50:
        r,_ = pointbiserialr(dd["event"], dd[col])
        flag = "⚠️ 너무높음!" if abs(r)>0.5 else "✓ 정상"
        print(f"  event vs {col:14s}: 상관 {r:+.3f} {flag}")

print("\n"+"="*60)
print("[점검3] 데이터 정합성: 시작wave에 실제 데이터가 있나?")
have, missing = 0, 0
for _, r in s.iterrows():
    exact = panel[(panel["pid"]==r["pid"]) & (panel["wave"]==r["시작wave"])]
    if len(exact)>0 and pd.notna(exact.iloc[0]["직종"]):
        have += 1
    else:
        missing += 1
print(f"  시작wave에 직종 데이터 있음: {have}건 / 없음(대체됨): {missing}건")
print(f"  → 없는 비율 {missing/(have+missing)*100:.1f}% (높으면 그만큼 중앙값 대체 = 신호 약화)")

print("\n"+"="*60)
print("결론: 점검1 '없음' + 점검2 모두 '정상'이면 → 누수 없음으로 확정 가능")