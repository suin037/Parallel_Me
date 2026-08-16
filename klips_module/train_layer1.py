# train_layer1.py — Layer 1: 룰베이스 조회 (GOMS 직종별 소득·이직률)
import pandas as pd

g = pd.read_csv("data/clean/goms_clean.csv")

def query_occupation(occupation=None, major_cat=None):
    """직종/전공 조건으로 평균소득·이직률 조회."""
    df = g.copy()
    if occupation is not None:
        df = df[df["occupation"] == occupation]
    if major_cat is not None:
        df = df[df["major_cat"] == major_cat]
    if len(df) == 0:
        return {"n": 0, "msg": "해당 조건 표본 없음"}
    return {
        "n": len(df),
        "직종명": df["occupation_name"].mode().iloc[0] if not df["occupation_name"].isna().all() else "-",
        "평균_현재소득": round(df["income_now"].mean(), 1),
        "평균_초임": round(df["income_first"].mean(), 1),
        "평균_소득변화율": round(df["income_change_pct"].mean(), 1),
        "이직률": round(df["changed_job"].mean() * 100, 1),
        "정규직비율": round((df["is_regular"] == 1).mean() * 100, 1),
    }

# 테스트: 직종코드별 요약
print("=== 직종별 요약 (상위 표본) ===")
for occ in g["occupation"].value_counts().head(8).index:
    r = query_occupation(occupation=occ)
    print(f"직종 {occ} ({r['직종명']}): 평균소득 {r['평균_현재소득']}만원 | 이직률 {r['이직률']}% | n={r['n']}")

# 전체 평균
print(f"\n전체 평균 현재소득: {g['income_now'].mean():.1f}만원")
print(f"전체 이직률: {g['changed_job'].mean()*100:.1f}%")