# check_pkl.py — 우리가 만든 .pkl들이 뭘 담고 있나 확인
import joblib, os
d = "backend/models/artifacts"
for f in sorted(os.listdir(d)):
    if f.endswith(".pkl"):
        try:
            obj = joblib.load(os.path.join(d, f))
            print(f"\n=== {f} ===")
            if isinstance(obj, dict):
                for k, v in obj.items():
                    print(f"  {k}: {type(v).__name__}", 
                          f"= {v}" if isinstance(v,(list,str,float,int)) else "")
            else:
                print(f"  (dict 아님) {type(obj).__name__}")
        except Exception as e:
            print(f"\n=== {f} === 로드실패: {e}")