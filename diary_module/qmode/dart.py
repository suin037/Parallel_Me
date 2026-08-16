# -*- coding: utf-8 -*-
"""dart.py — OpenDART(금융감독원 전자공시) 클라이언트.

기업 분석의 사실 근거를 여기서 가져온다. LLM이 지어내는 대신 공시 원문·재무 수치를
그대로 쓰고, 화면에도 출처를 함께 보여준다.

필요한 것: opendart.fss.or.kr 에서 발급한 무료 인증키(.env 의 DART_API_KEY).

세 가지만 쓴다.
  1) corpCode  — 기업명↔고유번호 매핑(ZIP 1회 내려받아 캐시). 이게 없으면 나머지가 안 된다.
  2) 주요계정  — 매출·영업이익·당기순이익 연도별.
  3) 공시목록  — 최근 공시 제목·날짜·원문 링크.
"""

from __future__ import annotations

import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "dart_corp_codes.json"      # 기업명→고유번호 캐시(gitignore 권장)
BASE = "https://opendart.fss.or.kr/api"
CACHE_MAX_AGE = 30 * 24 * 3600             # 30일


def api_key():
    try:
        import report_one as R1
        R1._load_dotenv()
    except Exception:      # noqa: BLE001
        pass
    return os.getenv("DART_API_KEY")


def _get(path, **params):
    key = api_key()
    if not key:
        raise RuntimeError("no_dart_key")
    params["crtfc_key"] = key
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as r:
        return r.read()


# ── 1) 기업명 → 고유번호 ────────────────────────────────────────────────
def _load_corp_cache():
    if CACHE.exists() and (time.time() - CACHE.stat().st_mtime) < CACHE_MAX_AGE:
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:      # noqa: BLE001
            pass
    return None


def build_corp_index(force=False):
    """corpCode.xml(ZIP)을 받아 {기업명: {corp_code, stock_code}} 로 캐시.

    11만 건이라 한 번 받아두고 30일 쓴다. 상장사(stock_code 있음)를 우선한다.
    """
    if not force:
        cached = _load_corp_cache()
        if cached:
            return cached
    raw = _get("corpCode.xml")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml = z.read(z.namelist()[0]).decode("utf-8")
    index = {}
    for m in re.finditer(r"<list>(.*?)</list>", xml, re.S):
        block = m.group(1)
        def pick(tag):
            g = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S)
            return (g.group(1).strip() if g else "")
        name, code, stock = pick("corp_name"), pick("corp_code"), pick("stock_code")
        if not name or not code:
            continue
        prev = index.get(name)
        # 같은 이름이면 상장사(종목코드 있음)를 우선한다.
        if prev and prev.get("stock_code") and not stock:
            continue
        index[name] = {"corp_code": code, "stock_code": stock}
    CACHE.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


def find_company(name, limit=5):
    """기업명으로 검색 — 정확 일치 우선, 없으면 부분 일치. 상장사를 앞에 둔다."""
    q = (name or "").strip()
    if not q:
        return []
    index = build_corp_index()
    if q in index:
        return [{"name": q, **index[q]}]
    hits = [{"name": k, **v} for k, v in index.items() if q in k]
    hits.sort(key=lambda x: (not x["stock_code"], len(x["name"])))
    return hits[:limit]


# ── 2) 재무 — 매출·영업이익·당기순이익 ──────────────────────────────────
# 공시 계정명 그대로 매칭 — 순이익은 '당기순이익(손실)' 로 온다.
_ACCOUNTS = {
    "매출액": "revenue",
    "영업이익": "operating",
    "당기순이익(손실)": "net",
    "당기순이익": "net",
    "자산총계": "assets",
    "부채총계": "liabilities",
    "자본총계": "equity",
}


def _to_num(v):
    try:
        return int(str(v).replace(",", "").strip())
    except Exception:      # noqa: BLE001
        return None


def financials(corp_code, years=5, reprt_code="11011"):
    """연도별 주요계정. reprt_code 11011 = 사업보고서(연간).

    최근 연도부터 거슬러 올라가며 조회한다(당해 사업보고서는 아직 없을 수 있음).
    """
    import datetime
    this_year = datetime.date.today().year
    out = []
    for y in range(this_year, this_year - years - 2, -1):
        if len(out) >= years:
            break
        try:
            data = json.loads(_get("fnlttSinglAcnt.json", corp_code=corp_code,
                                   bsns_year=str(y), reprt_code=reprt_code))
        except Exception:      # noqa: BLE001
            continue
        if data.get("status") != "000":
            continue
        row = {"year": y}
        for item in data.get("list", []):
            key = _ACCOUNTS.get((item.get("account_nm") or "").strip())
            # 연결(CFS) 우선, 없으면 개별(OFS)
            if key and item.get("fs_div", "CFS") in ("CFS", "OFS"):
                if key not in row or item.get("fs_div") == "CFS":
                    row[key] = _to_num(item.get("thstrm_amount"))
        if any(row.get(k) for k in ("revenue", "operating", "net")):
            out.append(row)
    return sorted(out, key=lambda r: r["year"])


# ── 3) 공시 목록 ────────────────────────────────────────────────────────
def disclosures(corp_code, days=90, limit=10):
    """최근 공시 — 제목·날짜·원문 링크(근거 자료로 화면에 그대로 보여준다)."""
    import datetime
    end = datetime.date.today()
    bgn = end - datetime.timedelta(days=days)
    try:
        data = json.loads(_get("list.json", corp_code=corp_code,
                               bgn_de=bgn.strftime("%Y%m%d"), end_de=end.strftime("%Y%m%d"),
                               page_count="100"))
    except Exception:      # noqa: BLE001
        return []
    if data.get("status") != "000":
        return []
    rows = []
    for it in data.get("list", [])[:limit]:
        rcept = it.get("rcept_no")
        rows.append({
            "title": it.get("report_nm"),
            "date": it.get("rcept_dt"),
            "submitter": it.get("flr_nm"),
            "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept}" if rcept else None,
        })
    return rows
