import { useState } from "react";
import { isPostingReady, extractFromUrl, extractFromPdf } from "../data/jobAnalysis.js";

// 공고 담기 — 입력 화면에서는 '모으기만' 한다. 분석 결과는 시뮬레이션을 돌린 뒤
// 결과 화면의 '공고 분석' 탭에서 보여준다(입력과 결과를 섞지 않는다).
// 여러 개 담으면 같은 성향 기준으로 나란히 비교된다.

/** 서버가 준 실패 이유 → 사용자가 무엇을 하면 되는지.
 *
 * 예전에는 어떤 이유든 "주소를 읽지 못했어요" 한 문장만 띄웠다. 주소가 잘못된 건지,
 * 그 공고가 만료된 건지, 우리 서버가 안 뜬 건지 구분할 수가 없어서 제보가 와도
 * 스크린샷만으로는 원인을 못 잡았다.
 */
function urlFailNote(reason) {
  const r = String(reason || "");
  if (r === "bad_url") return "주소 형식이 올바르지 않아요. http 로 시작하는 전체 주소를 넣어주세요.";
  if (r.startsWith("fetch_failed")) {
    return "그 주소를 열지 못했어요. 로그인해야 보이거나 만료된 공고일 수 있어요 — 본문을 붙여넣어 주세요.";
  }
  return "주소를 읽지 못했어요. 본문을 붙여넣어 주세요.";
}

/** 읽어온 게 '공고'인지까지 말해준다.
 *
 * source="page" 는 공고 구조화 정보(JobPosting)를 못 찾아 페이지 글자를 그대로 긁은 것이다.
 * 채용 포털 첫 화면을 넣으면 메뉴·안내문이 1,800자쯤 담기는데 thin 도 아니라서,
 * 예전에는 "잘 불러왔어요"라고 말하고 그 메뉴를 그대로 분석에 넘겼다.
 */
function readNote(data) {
  const who = `${data.company || ""} ${data.title || ""}`.trim();
  if (data.thin) {
    return `${who} — 제목만 읽혔어요. 이 사이트는 본문이 스크립트로 그려져서, 붙여넣으면 훨씬 정확해집니다.`.trim();
  }
  if (data.source === "page") {
    return `${who} — 공고 본문을 찾지 못해 페이지 글자를 그대로 가져왔어요 (${data.chars}자). `
      .trim() + "개별 공고 페이지 주소를 넣거나, 본문을 붙여넣는 쪽이 정확합니다.";
  }
  return `불러왔어요 (${data.chars}자). 빠진 부분은 아래에서 고쳐도 돼요.`;
}
export default function JobPostingInput({ postings, setPostings }) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState("paste");   // paste | url | pdf
  const [url, setUrl] = useState("");
  const [note, setNote] = useState(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(true);      // 입력칸 펼침(담은 게 없으면 항상 열림)
  const ready = isPostingReady(text);

  function labelOf(raw) {
    const first = String(raw).trim().split("\n")[0].replace(/\s+/g, " ");
    return first.length > 22 ? `${first.slice(0, 22)}…` : first || "공고";
  }

  function add() {
    if (!ready) return;
    setPostings([...(postings || []), { id: Date.now(), text: text.trim(), label: labelOf(text) }]);
    setText(""); setUrl(""); setNote(null); setOpen(false);
  }

  function remove(id) {
    const next = (postings || []).filter((p) => p.id !== id);
    setPostings(next);
    if (!next.length) setOpen(true);
  }

  async function loadUrl() {
    setBusy(true); setNote(null);
    try {
      const data = await extractFromUrl(url.trim());
      if (!data.ok) { setNote(urlFailNote(data.reason)); return; }
      setText(data.text || "");
      setNote(readNote(data));
    } catch {
      // 서버까지 못 갔을 때. 위(!data.ok)와 문구를 나눠야 한다 — 예전엔 같은 문장이라
      // '주소가 문제'인지 '서버가 문제'인지 화면만 보고는 알 수 없었다.
      setNote("서버에 연결하지 못했어요. 잠시 뒤 다시 시도하거나 본문을 붙여넣어 주세요.");
    } finally {
      setBusy(false);
    }
  }

  async function loadPdf(file) {
    if (!file) return;
    setBusy(true); setNote(null);
    try {
      const data = await extractFromPdf(file);
      if (!data.ok) { setNote(data.hint || "PDF에서 글자를 찾지 못했어요. 본문을 붙여넣어 주세요."); return; }
      setText(data.text || "");
      setNote(`PDF ${data.pages}쪽에서 ${data.chars}자를 읽었어요.`);
    } catch {
      setNote("PDF를 읽지 못했어요. 본문을 붙여넣어 주세요.");
    } finally {
      setBusy(false);
    }
  }

  const list = postings || [];

  return (
    <details className="smooth-details mt-3 rounded-2xl border border-white/10 bg-[#0B1423]/80 px-3.5 py-3">
      <summary className="cursor-pointer text-[11px] font-semibold text-sub">
        지원하려는 공고 담기 · 선택
        {list.length > 0 && <span className="ml-1 text-[10px] text-[#C7B5F2]">{list.length}개</span>}
      </summary>
      <div className="details-body">
        <div className="details-body-inner">
      <p className="mt-2 text-[10px] leading-relaxed text-mut">
        여기서는 담아두기만 해요. 시뮬레이션을 돌리면 결과 화면에서 요구 역량과
        <b className="text-sub"> 내 성향과 맞는 지점·부딪힐 지점</b>을 공고별로 보여드려요.
      </p>

      {list.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {list.map((p) => (
            <span key={p.id} className="flex items-center gap-1 rounded-full border border-[#8B6CCF]/40 bg-[#8B6CCF]/[.12] px-2.5 py-1 text-[10px] text-[#C7B5F2]">
              {p.label}
              <button type="button" onClick={() => remove(p.id)} className="tap text-mut hover:text-ink" aria-label="이 공고 빼기">×</button>
            </span>
          ))}
          {!open && (
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="tap rounded-full border border-dashed border-white/20 px-2.5 py-1 text-[10px] text-mut"
            >
              ＋ 공고 추가
            </button>
          )}
        </div>
      )}

      {open && (
        <>
          <div className="mt-2 flex gap-1.5">
            {[["paste", "붙여넣기"], ["url", "URL"], ["pdf", "PDF"]].map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => { setMode(key); setNote(null); }}
                className={`tap flex-1 rounded-lg border px-2 py-1.5 text-[10px] transition-colors ${
                  mode === key ? "border-[#8B6CCF] bg-[#8B6CCF]/15 text-[#C7B5F2]" : "border-white/10 text-sub"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {mode === "url" && (
            <div className="mt-2">
              <p className="mb-1.5 text-[9px] leading-4 text-mut">URL에서 공개된 공고 본문을 자동으로 읽어요. 로그인이나 화면 렌더링이 필요한 사이트는 본문 붙여넣기가 더 정확해요.</p>
              <div className="flex gap-1.5">
                <input
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="채용 공고 주소 붙여넣기"
                  className="min-w-0 flex-1 rounded-xl border border-line bg-bg px-3 py-2 text-[11px] text-ink outline-none placeholder:text-mut focus:border-cyan"
                />
                <button
                  type="button"
                  onClick={loadUrl}
                  disabled={!url.trim() || busy}
                  className="tap shrink-0 rounded-xl bg-white/10 px-3 text-[11px] font-bold text-ink disabled:opacity-40"
                >
                  본문 불러오기
                </button>
              </div>
            </div>
          )}

          {mode === "pdf" && (
            <input
              type="file"
              accept="application/pdf"
              onChange={(event) => loadPdf(event.target.files?.[0])}
              className="mt-2 w-full rounded-xl border border-line bg-bg px-3 py-2 text-[10px] text-sub file:mr-2 file:rounded-lg file:border-0 file:bg-[#8B6CCF] file:px-2 file:py-1 file:text-[10px] file:text-white"
            />
          )}

          {note && <p className="mt-1.5 text-[10px] leading-relaxed text-[#FFB36B]">{note}</p>}

          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={4}
            placeholder="채용 공고 본문을 붙여넣어 주세요 (주요 업무·자격 요건 포함)"
            className="mt-2 w-full resize-none rounded-xl border border-line bg-bg px-3 py-2.5 text-[11px] leading-relaxed text-ink outline-none placeholder:text-mut focus:border-cyan"
          />

          <div className="mt-2 flex gap-1.5">
            <button
              type="button"
              onClick={add}
              disabled={!ready || busy}
              className={`tap flex-1 rounded-xl py-2.5 text-[12px] font-bold transition-colors ${
                ready && !busy ? "bg-[#8B6CCF] text-white" : "bg-white/10 text-mut"
              }`}
            >
              {list.length ? "이 공고도 담기" : "이 공고 담기"}
            </button>
            {list.length > 0 && (
              <button
                type="button"
                onClick={() => { setOpen(false); setText(""); setNote(null); }}
                className="tap shrink-0 rounded-xl border border-white/10 px-3 text-[11px] text-sub"
              >
                취소
              </button>
            )}
          </div>
        </>
      )}
        </div>
      </div>
    </details>
  );
}
