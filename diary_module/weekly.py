"""
weekly.py — 주간 집계
일별 analyze() 결과들을 모아 리포트 재료 JSON 생성.
판단/해석은 하지 않는다. 정량 근거만 만들고 해석은 AI에 맡긴다.
"""
import numpy as np
from collections import Counter
from datetime import datetime


WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"]



def _peak_chunk(r):
    """감정 강도가 가장 센 청크 원문 (요약 아님, 원문 그대로)"""
    ch = r.get("chunks", [])
    if not ch:
        return None
    peak = max(ch, key=lambda c: abs(c["valence"]))
    t = peak["text"]
    return {"text": t[:90] + ("..." if len(t) > 90 else ""),
            "valence": peak["valence"], "coarse": peak["coarse"]}


def _keywords(r, top=4):
    """상황 단서가 되는 명사 (Kiwi 기반, 사건 파악용)"""
    try:
        from metrics import kiwi
    except ImportError:
        return []
    from collections import Counter
    STOP = {"오늘", "어제", "내일", "생각", "정말", "너무", "진짜", "사람",
            "하루", "때문", "이것", "그것", "동안", "이제", "다음", "자신"}
    txt = " ".join(c["text"] for c in r.get("chunks", []))
    c = Counter(t.form for t in kiwi.tokenize(txt)
                if t.tag.startswith("NN") and len(t.form) > 1 and t.form not in STOP)
    return [w for w, _ in c.most_common(top)]


def aggregate(entries):
    """
    entries: [{"date": "2026-07-20", "result": <analyze() 반환값>}, ...]
    """
    entries = sorted(entries, key=lambda e: e["date"])
    n = len(entries)
    if n == 0:
        return {"error": "no_entries"}

    daily, val_by_day = [], []
    coarse_c, fine_c, sit_c = Counter(), Counter(), Counter()
    neg_sit_c = Counter()
    ling_sum = Counter()
    crisis_days = []
    all_chunks = []

    for e in entries:
        r = e["result"]
        d = datetime.strptime(e["date"], "%Y-%m-%d")
        wd = WEEKDAY[d.weekday()]
        dom = r["dominant"]
        v = r["valence_mean"]

        daily.append({
            "date": e["date"], "weekday": wd,
            "coarse": dom["coarse"], "fine": dom["fine"],
            "conf": dom["conf"], "valence": v,
            "mixed_ratio": r.get("mixed_ratio", 0),
            "situation": r["situation"]["name"],
            "situation_conf": r["situation"]["conf"],
            "crisis_level": r.get("crisis_level", 0),
            "evidence": _peak_chunk(r),
            "keywords": _keywords(r),
        })
        val_by_day.append(v)

        coarse_c[dom["coarse"]] += 1
        fine_c[dom["fine"]] += 1
        # 상황은 신뢰도 낮으면 집계에서 제외 (S코드 오분류 방어)
        if r["situation"]["conf"] >= 0.5:
            sit_c[r["situation"]["name"]] += 1
            if v < 0:
                neg_sit_c[r["situation"]["name"]] += 1

        L = r.get("linguistic", {})
        for k in ("approach_count", "avoidant_count"):
            ling_sum[k] += L.get(k, 0)
        for k in ("first_person_ratio", "absolutist_ratio",
                  "insight_ratio", "emotion_density", "past_ratio"):
            ling_sum[k] += L.get(k, 0)

        if r.get("crisis_level", 0) >= 2:
            crisis_days.append(e["date"])

        # 감정 강도 최고 청크 (리포트 인용용)
        for c in r.get("chunks", []):
            all_chunks.append({"date": e["date"], **c})

    va = np.array(val_by_day, float)

    # 연속 부정 일수 (최대 구간)
    streak = cur = 0
    for v in va:
        cur = cur + 1 if v < 0 else 0
        streak = max(streak, cur)

    # 추세: 전반부 vs 후반부
    half = max(1, n // 2)
    trend = float(va[half:].mean() - va[:half].mean()) if n >= 2 else 0.0

    # 언어지표 주간 평균/합
    ling_week = {
        "approach_total": ling_sum["approach_count"],
        "avoidant_total": ling_sum["avoidant_count"],
        "coping_balance_week": round(
            (ling_sum["approach_count"] - ling_sum["avoidant_count"]) /
            max(ling_sum["approach_count"] + ling_sum["avoidant_count"], 1), 3),
    }
    for k in ("first_person_ratio", "absolutist_ratio",
              "insight_ratio", "emotion_density", "past_ratio"):
        ling_week[k + "_avg"] = round(ling_sum[k] / n, 4)

    # 인용 후보: 가장 부정적/긍정적 청크
    all_chunks.sort(key=lambda c: c["valence"])
    quotes = {
        "lowest": all_chunks[0] if all_chunks else None,
        "highest": all_chunks[-1] if all_chunks else None,
    }

    return {
        "period": {"start": entries[0]["date"], "end": entries[-1]["date"],
                   "n_entries": n},
        "valence": {
            "mean": round(float(va.mean()), 3),
            "std": round(float(va.std()), 3),
            "min": round(float(va.min()), 3),
            "max": round(float(va.max()), 3),
            "trend": round(trend, 3),
            "negative_days": int((va < 0).sum()),
            "max_negative_streak": streak,
            "series": [round(float(v), 3) for v in va],
        },
        "emotions": {
            "coarse_top": coarse_c.most_common(3),
            "fine_top": fine_c.most_common(5),
            "mixed_days": sum(1 for d in daily if d["mixed_ratio"] > 0.3),
        },
        "situations": {
            "all": sit_c.most_common(),
            "negative_context": neg_sit_c.most_common(3),
            "low_conf_excluded": n - sum(sit_c.values()),
        },
        "linguistic_week": ling_week,
        "crisis": {"days": crisis_days, "count": len(crisis_days)},
        "quotes": quotes,
        "daily": daily,
    }


def to_prompt_context(agg):
    """AI 리포트 생성용 텍스트 (팀원 파트로 넘길 형태)"""
    if "error" in agg:
        return "분석할 기록이 없습니다."
    v = agg["valence"]
    e = agg["emotions"]
    s = agg["situations"]
    L = agg["linguistic_week"]
    lines = [
        f"[기간] {agg['period']['start']} ~ {agg['period']['end']} ({agg['period']['n_entries']}건)",
        f"[정서가] 평균 {v['mean']}, 변동성 {v['std']}, 추세 {v['trend']:+.3f}",
        f"         부정일 {v['negative_days']}일, 최장 연속 {v['max_negative_streak']}일",
        f"         일별 {v['series']}",
        f"[감정] {', '.join(f'{k} {c}회' for k, c in e['coarse_top'])}",
        f"       세부: {', '.join(f'{k}({c})' for k, c in e['fine_top'])}",
        f"       혼재감정 {e['mixed_days']}일",
        f"[맥락] {', '.join(f'{k} {c}회' for k, c in s['all']) or '식별 불가'}",
        f"       부정정서 맥락: {', '.join(f'{k} {c}회' for k, c in s['negative_context']) or '없음'}",
        f"[언어] 능동표현 {L['approach_total']}회 / 회피표현 {L['avoidant_total']}회 "
        f"(균형 {L['coping_balance_week']:+.2f})",
        f"       통찰어 비율 {L['insight_ratio_avg']}, 절대주의어 {L['absolutist_ratio_avg']}",
    ]
    if agg["crisis"]["count"]:
        lines.append(f"[주의] 위기 신호 감지일: {agg['crisis']['days']}")
    lines.append("[일별 기록]")
    for d in agg["daily"]:
        kw = ", ".join(d["keywords"]) if d["keywords"] else "-"
        lines.append(f"  {d['date']}({d['weekday']}) {d['coarse']}/{d['fine']} "
                     f"v={d['valence']:+.2f} | 키워드: {kw}")
        if d["evidence"]:
            lines.append(f"      원문: \"{d['evidence']['text']}\"")
    return "\n".join(lines)


if __name__ == "__main__":
    from infer import DiaryAnalyzer
    az = DiaryAnalyzer()

    week = [
        ("2026-07-13", "채점하고 나니 애매한 점수다. 소수직렬이라 예측이 의미 없다는 게 더 불안하다. 집에 오니 잠도 안 오고 배도 안 고프다."),
        ("2026-07-14", "국어 논리가 무슨 말인지 모르겠다. 푸는 데 너무 오래 걸린다. 내가 이걸 풀 실력이 안 되는 것 같다."),
        ("2026-07-15", "할 일을 미루다 새벽에 처리하게 되고 자꾸 야식을 먹는다. 야식 안 먹기로 약속한 내 자신이 초라해진다."),
        ("2026-07-16", "개인적인 일이 터져서 정신이 나갔다. 밥도 안 넘어가서 죽만 사먹었다. 먹고 또 화장실 가서 울었다."),
        ("2026-07-17", "엄마가 힘내라고 부추전을 구워줬다. 이렇게 날 생각해주는 사람이 있는데 어떻게든 힘내야겠다고 생각했다."),
        ("2026-07-18", "모의고사 성적이 떴는데 처음으로 상위권에 들었다. 조금씩 성장하고 있나 보다. 신난다."),
        ("2026-07-19", "쉬운 건 없다. 무너지는 하루에 무너지지 않으려 노력한다. 돌이켜보니 사소한 일도 큰 행복으로 다가온다."),
    ]

    entries = [{"date": d, "result": az.analyze(t)} for d, t in week]
    agg = aggregate(entries)

    print(to_prompt_context(agg))
    print("\n" + "=" * 60)
    print("[일별]")
    for d in agg["daily"]:
        print(f"  {d['date']}({d['weekday']}) {d['coarse']}/{d['fine']:12s} "
              f"v={d['valence']:+.3f} {d['situation']}")
    print("\n[인용 후보]")
    q = agg["quotes"]
    if q["lowest"]:
        print(f"  최저: {q['lowest']['date']} v={q['lowest']['valence']} \"{q['lowest']['text'][:40]}...\"")
    if q["highest"]:
        print(f"  최고: {q['highest']['date']} v={q['highest']['valence']} \"{q['highest']['text'][:40]}...\"")


# ============ Ryff 6요인 축 (참고 지표) ============
SIT_TO_RYFF = {
    "대인관계·친구": "positive_relations", "연애·결혼": "positive_relations",
    "직장 내 소외": "positive_relations", "학교폭력·따돌림": "positive_relations",
    "직장·업무": "env_mastery", "학업·성적": "env_mastery",
    "가족관계": "autonomy", "자녀·배우자": "autonomy",
    "질병·건강": "self_acceptance", "노후·요양": "self_acceptance",
    "노화·건강": "self_acceptance", "은퇴": "purpose",
}
RYFF_NAME = {
    "self_acceptance": "자아수용", "positive_relations": "긍정적 대인관계",
    "autonomy": "자율성", "env_mastery": "환경 통제감",
    "purpose": "삶의 목적", "growth": "개인적 성장",
}


def ryff_scores(entries, min_conf=0.5):
    """상황별 valence -> Ryff 축 참고 점수(0~10). 정식 PWBS 척도 측정 아님."""
    from collections import defaultdict
    b = defaultdict(list)
    for e in entries:
        r = e["result"]
        if r["situation"]["conf"] < min_conf:
            continue
        ax = SIT_TO_RYFF.get(r["situation"]["name"])
        if ax:
            b[ax].append(r["valence_mean"])
    out = {}
    for ax, name in RYFF_NAME.items():
        vs = b.get(ax, [])
        out[name] = {
            "score": round((float(np.mean(vs)) + 1) * 5, 1) if vs else None,
            "n": len(vs),
            "confidence": "충분" if len(vs) >= 3 else ("낮음" if vs else "관찰 없음"),
        }
    return out
