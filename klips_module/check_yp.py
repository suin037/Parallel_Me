# check_yp.py — YP 데이터 구조 확인 + GOMS와 비교
import pandas as pd

goms = pd.read_csv("data/clean/goms_clean.csv")
yp = pd.read_csv("data/clean/yp_clean.csv")

print("=== GOMS 컬럼 ===")
print(list(goms.columns))
print(f"행: {len(goms)}")
print("\n=== YP 컬럼 ===")
print(list(yp.columns))
print(f"행: {len(yp)}")

print("\n=== 공통 컬럼 (합칠 수 있는 것) ===")
common = set(goms.columns) & set(yp.columns)
print(sorted(common))

print("\n=== GOMS에만 / YP에만 ===")
print("GOMS 전용:", sorted(set(goms.columns) - set(yp.columns)))
print("YP 전용:", sorted(set(yp.columns) - set(goms.columns)))

print("\n=== YP 샘플 (첫 3행) ===")
print(yp.head(3).to_string())

# yp_spells도 확인
sp = pd.read_csv("data/clean/yp_spells.csv")
print("\n=== yp_spells 컬럼 ===")
print(list(sp.columns))
print(f"행: {len(sp)}")
print(sp.head(3).to_string())