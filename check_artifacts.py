# check_artifacts.py
import glob, joblib, json, os

for f in glob.glob('**/*.pkl', recursive=True):
    print('='*60)
    print(f, f'{os.path.getsize(f)/1024:.0f}KB')
    try:
        m = joblib.load(f)
        print(type(m))
        # 메타데이터가 dict로 같이 저장돼 있는 경우
        if isinstance(m, dict):
            print('keys:', list(m.keys()))
    except Exception as e:
        print('load failed:', e)

for f in glob.glob('**/*report*.json', recursive=True):
    print('='*60, f)
    print(json.dumps(json.load(open(f, encoding='utf-8')),
                     ensure_ascii=False, indent=2)[:2000])