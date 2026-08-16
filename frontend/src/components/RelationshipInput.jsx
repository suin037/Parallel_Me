import { useState } from "react";
import { redactPII } from "../data/piiRedact.js";

// 관계 상담 입력 — 선택지가 '관계' 영역으로 잡히면 공고 담기 대신 이 칸이 나온다.
// 대화·연락 내역(붙여넣기 또는 화면 캡처)을 담아두면, 시뮬레이션 후 결과에서 관계 분석을 보여준다.
// 특정 메신저를 지목하지 않는다 — 문자·DM·메신저 무엇이든 같은 방식으로 받는다.
//
// 프라이버시: 대화는 가장 민감한 기록이라 두 겹으로 다룬다.
//   1) 보내기 전 이름·전화번호·주소 등을 프론트에서 마스킹(redactPII)
//   2) 서버 저장 시 at-rest 암호화(Fernet) — DB가 통째로 새도 키 없이는 못 읽는다
// 그리고 담기 전까지는 브라우저 밖으로 나가지 않는다.
const TAGS = ["연인", "가족", "친구", "동료", "기타"];

export default function RelationshipInput({ talks, setTalks }) {
  const [text, setText] = useState("");
  const [tag, setTag] = useState("연인");
  const [images, setImages] = useState([]);   // [{name, media_type, data(base64)}]
  const [open, setOpen] = useState(true);
  const [note, setNote] = useState(null);
  const list = talks || [];
  const ready = text.trim().length >= 20 || images.length > 0;

  async function pickImages(files) {
    const picked = [...(files || [])].slice(0, 3);
    const read = await Promise.all(
      picked.map(
        (f) =>
          new Promise((res) => {
            const fr = new FileReader();
            fr.onload = () => res({ name: f.name, media_type: f.type, data: String(fr.result).split(",")[1] });
            fr.onerror = () => res(null);
            fr.readAsDataURL(f);
          }),
      ),
    );
    const ok = read.filter(Boolean);
    setImages(ok);
    setNote(ok.length ? `캡처 ${ok.length}장 준비됐어요. 공유하기 전까지는 이 브라우저에만 있어요.` : null);
  }

  function add() {
    if (!ready) return;
    setTalks([
      ...list,
      {
        id: Date.now(),
        tag,
        // 보내기 전에 개인정보를 지운다 — 이름·번호가 서버로 가지 않게.
        transcript: redactPII(text.trim()),
        images,
        label: `${tag} · ${images.length ? `캡처 ${images.length}장` : `대화 ${text.trim().length}자`}`,
      },
    ]);
    setText(""); setImages([]); setNote(null); setOpen(false);
  }

  function remove(id) {
    const next = list.filter((t) => t.id !== id);
    setTalks(next);
    if (!next.length) setOpen(true);
  }

  return (
    <details className="mt-3 rounded-2xl border border-white/10 bg-[#0B1423]/80 px-3.5 py-3" open>
      <summary className="cursor-pointer text-[11px] font-semibold text-sub">
        대화·연락 내역 공유 · 선택
        {list.length > 0 && <span className="ml-1 text-[10px] text-[#C7B5F2]">{list.length}개</span>}
      </summary>
      <p className="mt-2 text-[10px] leading-relaxed text-mut">
        대화 내역이나 연락 내역을 공유해 주시면, 시뮬레이션 후 결과에서 <b className="text-sub">이 관계에서
        오가는 신호와 당신의 성향</b>을 함께 짚어드려요. 이름·연락처는 보내기 전에 자동으로 가려지고,
        서버에는 암호화해 보관합니다.
      </p>

      {list.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {list.map((t) => (
            <span key={t.id} className="flex items-center gap-1 rounded-full border border-[#8B6CCF]/40 bg-[#8B6CCF]/[.12] px-2.5 py-1 text-[10px] text-[#C7B5F2]">
              {t.label}
              <button type="button" onClick={() => remove(t.id)} className="tap text-mut hover:text-ink" aria-label="이 대화 빼기">×</button>
            </span>
          ))}
          {!open && (
            <button type="button" onClick={() => setOpen(true)} className="tap rounded-full border border-dashed border-white/20 px-2.5 py-1 text-[10px] text-mut">
              ＋ 내역 추가
            </button>
          )}
        </div>
      )}

      {open && (
        <>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {TAGS.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTag(t)}
                className={`tap rounded-full border px-2.5 py-1 text-[10px] transition-colors ${
                  tag === t ? "border-[#8B6CCF] bg-[#8B6CCF]/20 text-[#C7B5F2]" : "border-white/10 text-sub"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={4}
            placeholder="주고받은 대화를 붙여넣어 주세요. (길면 최근 부분만으로도 충분해요)"
            className="mt-2 w-full resize-none rounded-xl border border-line bg-bg px-3 py-2.5 text-[11px] leading-relaxed text-ink outline-none placeholder:text-mut focus:border-[#8B6CCF]"
          />

          <label className="mt-2 block">
            <span className="mb-1 block text-[10px] text-mut">또는 대화 화면 캡처 (최대 3장)</span>
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={(event) => pickImages(event.target.files)}
              className="w-full rounded-xl border border-line bg-bg px-3 py-2 text-[10px] text-sub file:mr-2 file:rounded-lg file:border-0 file:bg-[#8B6CCF] file:px-2 file:py-1 file:text-[10px] file:text-white"
            />
          </label>

          {note && <p className="mt-1.5 text-[10px] leading-relaxed text-[#C7B5F2]">{note}</p>}

          <div className="mt-2 flex gap-1.5">
            <button
              type="button"
              onClick={add}
              disabled={!ready}
              className={`tap flex-1 rounded-xl py-2.5 text-[12px] font-bold transition-colors ${
                ready ? "bg-[#8B6CCF] text-white" : "bg-white/10 text-mut"
              }`}
            >
              {list.length ? "이 내역도 공유하기" : "이 내역 공유하기"}
            </button>
            {list.length > 0 && (
              <button type="button" onClick={() => { setOpen(false); setText(""); setImages([]); setNote(null); }} className="tap shrink-0 rounded-xl border border-white/10 px-3 text-[11px] text-sub">
                취소
              </button>
            )}
          </div>

          <p className="mt-2 text-[9px] leading-relaxed text-mut">
            상대를 평가하거나 관계를 진단하지 않습니다. 위기 신호가 보이면 분석 대신 도움받을 수 있는 곳을 안내해요.
          </p>
        </>
      )}
    </details>
  );
}
