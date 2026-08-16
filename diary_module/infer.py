# infer.py — 일기 통합 분석
import re, json, torch
import numpy as np
import torch.nn.functional as F
from transformers import AutoTokenizer
from train_v2 import Model
import slang, metrics

DEV = "cuda" if torch.cuda.is_available() else "cpu"

# 클래스별 검증 F1 (신뢰도 참고용)
COARSE_F1 = {"E10": .825, "E20": .760, "E30": .787,
             "E40": .714, "E50": .765, "E60": .974}

# 위기 패턴 (crisis.py 없을 때 대비 — 있으면 그거 씀)
try:
    import crisis
    HAS_CRISIS = True
except ImportError:
    HAS_CRISIS = False


class DiaryAnalyzer:
    def __init__(self, ckpt="./ckpt_e6/best.pt", taxonomy="emotion_taxonomy.json"):
        self.tax = json.load(open(taxonomy, encoding="utf-8"))
        # weights_only=False: 자체 학습 체크포인트(신뢰됨). torch>=2.6 기본값 대응.
        ck = torch.load(ckpt, map_location=DEV, weights_only=False)
        self.maps = ck["maps"]
        self.c_codes = sorted(self.maps["coarse"])
        self.f_codes = sorted(self.maps["fine"])
        self.s_codes = sorted(self.maps["sit"])

        hier = torch.zeros(len(self.maps["coarse"]), len(self.maps["fine"]))
        for c, i in self.maps["fine"].items():
            hier[self.maps["coarse"][self.tax["fine"][c]["coarse"]], i] = 1

        self.model = Model(ck["backbone"], len(self.maps["coarse"]),
                           len(self.maps["fine"]), len(self.maps["sit"]), hier.to(DEV))
        self.model.load_state_dict(ck["state"])
        self.model.to(DEV).eval()
        self.tok = AutoTokenizer.from_pretrained(ck["backbone"])

    # ---- 청크 분할: 학습 분포(평균 55토큰 ≈ 3문장)에 맞춤 ----
    def split_chunks(self, text, n_sent=4, overlap=1, max_chars=350):
        sents = re.split(r"(?<=[.!?。])\s+|\n+", text.strip())
        sents = [s.strip() for s in sents if len(s.strip()) > 1]
        if not sents:
            return []
        chunks, i = [], 0
        while i < len(sents):
            c = " ".join(sents[i:i + n_sent])[:max_chars]
            if len(c) > 3:
                chunks.append(c)
            i += max(1, n_sent - overlap)
        return chunks

    @torch.no_grad()
    def _predict(self, texts):
        enc = self.tok(texts, truncation=True, max_length=128,
                       padding=True, return_tensors="pt").to(DEV)
        with torch.cuda.amp.autocast(enabled=DEV == "cuda"):
            lc, lf, ls, lv = self.model(enc["input_ids"], enc["attention_mask"],
                                        hard_mask=True)
        return (F.softmax(lc, -1).float().cpu().numpy(),
                F.softmax(lf, -1).float().cpu().numpy(),
                F.softmax(ls, -1).float().cpu().numpy(),
                lv.float().cpu().numpy())

    def analyze(self, text):
        # 1) 위기 체크 (원문 기준)
        if HAS_CRISIS:
            cr = crisis.detect(text)
            c_level, c_block = cr.level, cr.block_report
        else:
            c_level, c_block = 0, False

        # 2) 슬랭 정규화
        norm_text, slang_hits = slang.normalize_slang(text)
        slang_info = slang.slang_polarity(text)

        # 3) 청크 분할
        chunks = self.split_chunks(norm_text)
        if not chunks:
            return {"error": "empty", "crisis_level": c_level}

        # 4) 감정 모델
        pc, pf, ps, vad = self._predict(chunks)

        per_chunk = []
        for i, ch in enumerate(chunks):
            ci = int(pc[i].argmax())
            top2 = np.sort(pc[i])[-2:]
            per_chunk.append({
                "text": ch,
                "coarse": self.tax["coarse"][self.c_codes[ci]],
                "conf": round(float(pc[i].max()), 3),
                "valence": round(float(vad[i][0]), 3),
                "arousal": round(float(vad[i][1]), 3),
                "mixed": bool(top2[1] - top2[0] < 0.15),
            })

        # 5) 문서 집계 (길이 가중)
        w = np.array([len(c) for c in chunks], float); w /= w.sum()
        doc_c = (pc * w[:, None]).sum(0)
        doc_f = (pf * w[:, None]).sum(0)
        doc_s = (ps * w[:, None]).sum(0)
        ci = int(doc_c.argmax())
        code_c = self.c_codes[ci]

        mask = np.array([self.tax["fine"][f]["coarse"] == code_c for f in self.f_codes])
        fi = int(np.where(mask, doc_f, -1).argmax())
        si = int(doc_s.argmax())
        sit_code = self.s_codes[si]

        # 6) 언어지표 (정규화된 전문 기준)
        ling = metrics.analyze_text(norm_text)

        val_series = [c["valence"] for c in per_chunk]

        return {
            "crisis_level": c_level,
            "block_report": c_block,
            "dominant": {
                "coarse": self.tax["coarse"][code_c],
                "display": self.tax.get("display_merge", {}).get("map", {}).get(
                    self.tax["coarse"][code_c], self.tax["coarse"][code_c]),
                "coarse_code": code_c,
                "conf": round(float(doc_c.max()), 3),
                "reliability": COARSE_F1.get(code_c, 0.8),
                "fine": self.tax["fine"][self.f_codes[fi]]["name"],
                "fine_conf": round(float(doc_f[fi]), 3),
            },
            "situation": {
                "code": sit_code,
                "name": self.tax.get("situation", {}).get(sit_code, sit_code),
                "conf": round(float(doc_s.max()), 3),
            },
            "valence_mean": round(float(np.average(val_series, weights=w)), 3),
            "valence_series": val_series,
            "valence_std": round(float(np.std(val_series)), 3),
            "mixed_ratio": round(float(np.mean([c["mixed"] for c in per_chunk])), 3),
            "coarse_dist": {self.tax["coarse"][self.c_codes[i]]: round(float(doc_c[i]), 3)
                            for i in range(len(doc_c))},
            "linguistic": ling,
            "interpret": metrics.interpret(ling),
            "rag_triggers": metrics.rag_triggers(ling),
            "slang": slang_info,
            "n_chunks": len(chunks),
            "chunks": per_chunk,
        }


if __name__ == "__main__":
    az = DiaryAnalyzer()
    tests = [
        "오늘 발표를 망쳤다. 손이 떨려서 말이 자꾸 꼬였다. 끝나고 화장실에 한참 있었다. "
        "그래도 저녁에 친구가 밥 사줘서 조금 풀렸다. 내일은 나아지겠지.",
        "그냥 다 귀찮다. 하기 싫어서 계속 미뤘다. 나중에 하지 뭐.",
        "그 카페 완전 야르였다 ㅋㅋ 분위기 미쳤음. 오랜만에 기분 좋았다.",
    ]
    for t in tests:
        r = az.analyze(t)
        print("\n" + "=" * 60)
        print(t[:50])
        print(f"  감정: {r['dominant']['coarse']} / {r['dominant']['fine']} "
              f"(conf {r['dominant']['conf']})")
        print(f"  상황: {r['situation']['name']}")
        print(f"  valence: {r['valence_mean']} 궤적={r['valence_series']}")
        print(f"  언어: {r['interpret']}")
        print(f"  RAG: {r['rag_triggers']}")
        print(f"  슬랭: {r['slang']['slang_hits']}")
        print(f"  위기: L{r['crisis_level']}")