from huggingface_hub import HfApi

REPO = "JY0/lifenology-diary-emotion"
api = HfApi()
api.create_repo(REPO, private=True, exist_ok=True)

api.upload_file(path_or_fileobj="model_v3_e6.pt",
                path_in_repo="best.pt", repo_id=REPO)
api.upload_file(path_or_fileobj="diary_module/emotion_taxonomy.json",
                path_in_repo="emotion_taxonomy.json", repo_id=REPO)

print("done:", f"https://huggingface.co/{REPO}")