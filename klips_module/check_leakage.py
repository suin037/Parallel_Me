# check_leakage.py — 시점 정합성 & leakage 점검
import pandas as pd
s = pd.read_pickle("data/klips_base_생존.pkl")
b = pd.read_pickle("data/klips_base.pkl")
h = pd.read_pickle("data/klips_health.pkl")

print("=== 생존테이블 구조 ===")
print(s[["pid","시작wave","끝wave","duration","event"]].head())
print("\n시작wave 범위:", s["시작wave"].min(), "~", s["시작wave"].max())

# 생존테이블의 '시작wave'가 실제로 spell '시작' 시점인지 확인
print("\n=== base와 join 시 시점 확인 ===")
sample = s.iloc[0]
pid = sample["pid"]
print(f"pid {pid}: 시작wave={sample['시작wave']}, duration={sample['duration']}, event={sample['event']}")
print("이 사람의 base 기록 (wave별):")
print(b[b["pid"]==pid][["wave","직종","월임금_실질","이직"]].to_string())

# 핵심 질문: 시작wave 시점의 값을 쓰는데, 그 값이 '미래' 정보를 포함하나?
print("\n=== leakage 위험 체크 ===")
print("만약 시작wave의 만족도/임금이 spell 시작 시점 값이면 OK")
print("만약 그게 이직 후 값이면 leakage (예측에 미래정보 사용)")