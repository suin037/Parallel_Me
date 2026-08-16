# -*- coding: utf-8 -*-
"""media.py — 일기에서 읽은 취향·기분으로 '실제로 있는 노래'를 골라 준다.

두 단계로 나눈 이유가 핵심이다.
  1) LLM 은 취향과 기분만 읽는다 — 일기에 나온 아티스트, 지금 기분, 어느 쪽으로
     기분을 옮기면 좋을지(그대로 머물기/천천히 끌어올리기/기운 내기).
  2) 곡은 Deezer 가 준다 — 제목·아티스트·링크·발매일이 전부 실재하는 값이다.
  3) 마지막 고르기도 LLM 이 하되, '실재하는 후보 목록 안에서만' 고르게 한다.

그래서 곡명을 지어낼 수가 없다. 전에는 모델 지식만으로 곡을 말해서 없는 노래가
나올 위험이 있었고, 그걸 검색어로 돌려 사용자에게 확인을 떠넘겼다.

Deezer 공개 API 는 키·인증이 필요 없다. 다만 호출이 잦으면 429 가 나므로
같은 씨앗은 캐시해서 다시 부르지 않는다.

한계: Deezer 는 곡의 밝기/에너지 수치를 주지 않는다(스포티파이 audio-features 는
신규 앱에 막혔다). 그래서 '기분에 맞는 정도'는 음향 분석이 아니라 아티스트 유사도 +
LLM 판단이다. 측정이 아니라는 뜻이고, 화면에도 그렇게 밝힌다.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIARY = HERE.parent
ROOT = DIARY.parent
for p in (str(DIARY), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

DEEZER = "https://api.deezer.com"
_UA = {"User-Agent": "parallel-me/1.0"}

# 같은 씨앗으로 또 부르지 않게. 프로세스 메모리면 충분하다(하루 1회 쓰는 기능).
_CACHE: dict[str, tuple[float, object]] = {}
_TTL = 60 * 60 * 6


def _get(path, **params):
    key = path + "?" + urllib.parse.urlencode(params)
    hit = _CACHE.get(key)
    now = time.time()
    if hit and now - hit[0] < _TTL:
        return hit[1]
    url = DEEZER + key
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.load(r)
    except Exception:      # noqa: BLE001 — 한 곡 못 가져온다고 전체가 죽으면 안 된다
        return None
    if isinstance(data, dict) and data.get("error"):
        return None
    _CACHE[key] = (now, data)
    return data


def _client():
    try:
        import report_one as R1
        R1._load_dotenv()
    except Exception:      # noqa: BLE001
        pass
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        from anthropic import Anthropic
        return Anthropic()
    except ImportError:
        return None


# ── 1단계: 일기 → 씨앗(취향)과 기분 ─────────────────────────────
_SEED_SYSTEM = (
    "너는 사용자의 최근 일기를 읽고 음악 추천의 '씨앗'을 뽑는 사람이다.\n"
    "- artists: 일기에 실제로 언급된 가수·밴드 이름만(없으면 빈 배열). 추측해 넣지 마라.\n"
    "- fallback: 일기에 언급이 없을 때 쓸 씨앗 — 지금 기분·방향에 어울리는 '실존하는'\n"
    "  가수·밴드 이름 3개. 한국 사용자이니 한국 아티스트를 우선 넣되 확실히 실존하는\n"
    "  이름만 써라(존재를 확신 못 하면 넣지 마라). 곡 제목이 아니라 아티스트 이름이다.\n"
    "- moodNow: 지금 기분을 한 단어로.\n"
    '- shift  : "stay"(그 기분에 머물게) | "lift"(천천히 끌어올리기) | "energize"(기운 내기)\n'
    "  기분이 많이 가라앉은 날엔 갑자기 신나는 쪽으로 밀지 마라. 대개 stay 나 lift 다.\n"
    "- why    : 왜 그렇게 봤는지 1문장(기록의 구체적 사실로).\n"
    'JSON만: {"artists": [], "fallback": [], "moodNow": "", "shift": "", "why": ""}'
)

# ── 3단계: 실재 후보 안에서 고르기 ──────────────────────────────
_PICK_SYSTEM = (
    "너는 실제로 존재하는 곡 목록 중에서 지금 이 사람에게 건넬 3곡을 고르는 사람이다.\n"
    "\n"
    "규칙\n"
    "1) 반드시 아래 후보 목록의 번호로만 고른다. 목록에 없는 곡을 지어내지 마라.\n"
    "2) 지금 기분과 옮기고 싶은 방향(shift)에 맞춰 골라라. 가라앉은 날에 갑자기\n"
    "   신나는 곡을 밀지 마라 — 먼저 곁에 있어주는 곡이 낫다.\n"
    "3) 세 곡을 서로 다르게: 아는 결 하나, 새로 만나는 것 하나, 나머지 하나.\n"
    "4) why 는 1문장. 일기의 구체적 사실이나 씨앗 아티스트와 이어서 말해라.\n"
    "5) 음향 분석 수치가 있는 게 아니다. '이 곡이 과학적으로 기분을 올린다'처럼\n"
    "   말하지 마라. 진단·처방 금지. 한국어로만.\n"
    'JSON만: {"picks": [{"i": 0, "why": "..."}]}'
)

_SPEECH = {
    "polite": "존댓말('~요/~예요')로 쓴다.",
    "casual": "친근한 반말로 쓴다. '~요/~예요' 를 쓰지 마라.",
}


def _ask_json(client, system, user, max_tokens=900):
    resp = client.messages.create(
        model="claude-sonnet-5", max_tokens=max_tokens, system=system,
        thinking={"type": "disabled"},
        messages=[{"role": "user", "content": user}])
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    i, j = raw.find("{"), raw.rfind("}")
    return json.loads(raw[i:j + 1]) if i >= 0 and j > i else {}


def _artist_id(name):
    """이름 → 아티스트 id. 팬 수가 가장 많은 항목을 고른다.

    1순위를 그냥 쓰면 안 된다 — 'Coldplay' 검색 1순위가 팬 74명짜리 껍데기 계정이고
    진짜 Coldplay(팬 1,834만)는 2순위였다. 껍데기는 관련 아티스트도 대표곡도 없어
    후보가 통째로 비었다(외국 아티스트에서 특히 잦다).
    """
    d = _get("/search/artist", q=name, limit=8)
    rows = [r for r in ((d or {}).get("data") or []) if r.get("id")]
    if not rows:
        return None
    # 이름이 정확히 같은 것 우선, 그 안에서 팬 수 최대.
    key = lambda r: (r.get("name", "").strip().lower() == name.strip().lower(),  # noqa: E731
                     r.get("nb_fan") or 0)
    return max(rows, key=key)["id"]


def _artist_genres(artist_id):
    """그 아티스트의 장르 — 앨범에 붙은 값이라 사실이다(추론이 아니다)."""
    alb = _get("/artist/%d/albums" % artist_id, limit=3)
    names = []
    for a in ((alb or {}).get("data") or [])[:2]:
        full = _get("/album/%d" % a["id"])
        for g in (((full or {}).get("genres") or {}).get("data") or []):
            if g.get("name") and g["name"] not in names:
                names.append(g["name"])
    return names[:3]


def _newest_album(artist_id):
    d = _get("/artist/%d/albums" % artist_id, limit=25)
    rows = [a for a in ((d or {}).get("data") or []) if a.get("release_date")]
    if not rows:
        return None
    return sorted(rows, key=lambda a: a["release_date"])[-1]


# 저작권프리 라이브러리 음원은 rank 가 바닥이다. 사람들이 실제로 듣는 곡만 남긴다.
_MIN_RANK = 90_000


def _tracks_for(artist_id, artist_name, want_new=True, genres=None):
    """그 아티스트의 대표곡 + (가능하면) 최신 앨범 수록곡. 전부 실재하는 값이다."""
    out = []
    gs = genres if genres is not None else _artist_genres(artist_id)
    top = _get("/artist/%d/top" % artist_id, limit=2)
    for t in ((top or {}).get("data") or []):
        if (t.get("rank") or 0) < _MIN_RANK:
            continue
        out.append({"title": t.get("title"), "artist": artist_name, "genres": gs,
                    "link": t.get("link"), "cover": (t.get("album") or {}).get("cover_medium"),
                    "year": None, "kind": "대표곡"})
    if want_new:
        alb = _newest_album(artist_id)
        if alb:
            full = _get("/album/%d" % alb["id"])
            year = (alb.get("release_date") or "")[:4]
            for t in ((full or {}).get("tracks") or {}).get("data", [])[:2]:
                out.append({"title": t.get("title"), "artist": artist_name, "genres": gs,
                            "link": t.get("link"), "cover": alb.get("cover_medium"),
                            "year": year, "album": alb.get("title"), "kind": "최근 앨범"})
    return out


def _candidates(seeds, fallback, limit_artists=4):
    """씨앗 아티스트 → 비슷한 아티스트 → 후보곡.

    일기에 언급된 아티스트가 없으면 fallback(모델이 댄 실존 아티스트)을 씨앗으로 쓴다.
    분위기·장르어로 곡을 '검색'하면 안 된다 — Deezer 검색은 제목·설명을 훑기 때문에
    "Upbeat Indie Pop — David G. Steele" 같은 저작권프리 라이브러리 음원이 올라온다.
    아티스트를 먼저 실재 확인하고 그 사람의 곡을 가져와야 실제로 듣는 노래가 나온다.
    """
    pool, seen, seed_genres = [], set(), []

    def push(rows):
        for t in rows:
            key = (t.get("title"), t.get("artist"))
            if not t.get("title") or not t.get("link") or key in seen:
                continue
            seen.add(key)
            pool.append(t)

    def harvest(names, tag_own=True):
        for name in names[:3]:
            aid = _artist_id(name)
            if not aid:
                continue      # 실재 확인 실패 — 조용히 버린다
            gs = _artist_genres(aid)
            if tag_own:
                for g in gs:
                    if g not in seed_genres:
                        seed_genres.append(g)      # 취향 장르 = 씨앗 아티스트의 장르(사실값)
                push(_tracks_for(aid, name, want_new=False, genres=gs))   # 씨앗 본인 곡
            rel = _get("/artist/%d/related" % aid, limit=limit_artists)
            for ar in ((rel or {}).get("data") or [])[:limit_artists]:
                push(_tracks_for(ar["id"], ar.get("name") or "?"))

    harvest((seeds or [])[:2])
    if not pool:
        harvest(fallback or [])
    return pool, seed_genres


def _recency_score(t):
    """최신 가점 — 올해에 가까울수록 높게. 발매일을 모르면 중립."""
    if not t.get("year"):
        return .35
    try:
        gap = date.today().year - int(t["year"])
    except (TypeError, ValueError):
        return .35
    if gap <= 0:
        return 1.0
    if gap >= 8:
        return .1
    return max(.1, 1.0 - gap * .11)


def tracks(records, speech="polite", limit=3):
    """일기 → 실재하는 추천곡 3개. {ok, items:[{title, artist, link, cover, year, why}]}"""
    sp = "casual" if speech == "casual" else "polite"
    lines = []
    for r in (records or [])[:12]:
        text = (r.get("text") or "").strip()
        if not text:
            continue
        meta = f" (기분{r.get('mood')}/5)" if r.get("mood") else ""
        lines.append(f"- {r.get('date') or '?'}: {text[:140]}{meta}")
    if not lines:
        return {"ok": False, "reason": "며칠 기록이 모이면 노래를 골라볼게요."}
    client = _client()
    if client is None:
        return {"ok": False, "reason": "서버가 꺼져 있어 노래를 고르지 못했어요."}

    # 1단계 — 취향과 기분만 읽는다.
    try:
        seed = _ask_json(client, _SEED_SYSTEM, "[최근 일기]\n" + "\n".join(lines), 500)
    except Exception:      # noqa: BLE001
        seed = {}
    artists = [str(a).strip() for a in (seed.get("artists") or []) if str(a).strip()]
    fallback = [str(a).strip() for a in (seed.get("fallback") or []) if str(a).strip()]
    shift = seed.get("shift") or "stay"

    # 2단계 — 실재하는 후보를 모은다.
    pool, seed_genres = _candidates(artists, fallback)
    if not pool:
        return {"ok": False, "reason": "지금은 어울리는 곡을 찾지 못했어요. 며칠 뒤 다시 볼게요."}
    pool.sort(key=_recency_score, reverse=True)
    pool = pool[:24]

    # 3단계 — 그 목록 안에서만 고르게 한다. 지어낼 수가 없다.
    listing = "\n".join(
        f"{i}. {t['title']} — {t['artist']}"
        + (f" ({t['year']}, {t.get('album','')})" if t.get("year") else "")
        + f" [{t.get('kind','')}]"
        for i, t in enumerate(pool))
    user = (f"[지금 기분] {seed.get('moodNow') or '알 수 없음'} / 옮기고 싶은 방향: {shift}\n"
            f"[씨앗 아티스트] {', '.join(artists) if artists else '일기에 없음'}\n\n"
            "[최근 일기]\n" + "\n".join(lines) + "\n\n[후보 곡]\n" + listing
            + f"\n\n위 후보 중에서 {limit}곡을 골라줘.")
    try:
        picked = _ask_json(client, _PICK_SYSTEM + "\n\n" + _SPEECH[sp], user, 700)
    except Exception:      # noqa: BLE001
        picked = {}

    items = []
    for p in (picked.get("picks") or []):
        try:
            t = pool[int(p.get("i"))]
        except (TypeError, ValueError, IndexError):
            continue
        items.append({**t, "why": str(p.get("why") or "").strip()})
        if len(items) >= limit:
            break
    if not items:      # 고르기가 실패해도 실재하는 후보는 있다 — 최신순 앞에서 채운다
        items = [{**t, "why": ""} for t in pool[:limit]]
    return {"ok": True, "items": items, "shift": shift, "genres": seed_genres,
            "seeds": artists, "moodNow": seed.get("moodNow") or "",
            "seedWhy": str(seed.get("why") or "").strip()}
