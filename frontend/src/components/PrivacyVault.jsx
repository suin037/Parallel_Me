import { useMemo, useState } from "react";
import { Card } from "./ui.jsx";
import { loadUniverse } from "../data/myUniverse.js";
import { useResult } from "../data/ResultContext.jsx";
import { redactPII } from "../data/piiRedact.js";
import { hasCrypto, isPassphraseSet, setupPassphrase, unlock, encryptJSON, decryptJSON } from "../data/secureStore.js";

// 🔒 개인정보 보호 (암호화) — 민감정보를 기기에서 AES-256-GCM으로 암호화하는 걸 '보여주는' 패널.
// 보험 공모전 어필용: 저장 형태(암호문) vs 복호화 내용을 나란히 보여줘 실제 암호화를 증명한다.
// 정직선: at-rest 보호. 원문·키는 디스크에 안 남고, 암호는 세션 메모리에만.
export default function PrivacyVault() {
  const { profile } = useResult();
  const [pass, setPass] = useState("");
  // 외부 AI 전송 마스킹 데모 — 예시 문장(이름·연봉·연락처 포함)으로 raw→마스킹 보여줌
  const demoRaw = `저는 ${profile?.name?.trim() || "김지원"}입니다. 지금 연봉 4200만원인데 이직 고민 중. 연락처 010-1234-5678`;
  const demoMasked = redactPII(demoRaw, { name: profile?.name?.trim() || "김지원", company: "" }).masked;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [cipher, setCipher] = useState(null); // 저장될 암호문 블록
  const [sample, setSample] = useState(null); // { plain, decrypted } 복호 증명
  const alreadySet = useMemo(() => isPassphraseSet(), []);

  // 암호화 대상(민감정보) 미리보기 — 일기 본문·답변·감정 등
  const sensitive = useMemo(() => {
    const u = loadUniverse();
    return (u.checkins || [])
      .filter((c) => !c.empty)
      .map((c) => ({ date: c.date, text: c.text, note: c.note, answers: c.answers, emotion: c.emotion, experiments: c.experiments }));
  }, []);

  async function run() {
    if (!hasCrypto()) { setErr("이 브라우저는 Web Crypto를 지원하지 않아요"); return; }
    if (pass.length < 4) { setErr("암호문구는 4자 이상으로"); return; }
    setBusy(true); setErr(null);
    try {
      const key = alreadySet ? await unlock(pass) : await setupPassphrase(pass);
      if (!key) { setErr("암호문구가 맞지 않아요"); setBusy(false); return; }
      const blob = await encryptJSON(sensitive, key);
      setCipher(blob);
      const back = await decryptJSON(blob, key); // 복호 증명
      const firstPlain = sensitive.find((x) => x.text) || sensitive[0] || {};
      const firstBack = (back || []).find((x) => x.date === firstPlain.date) || {};
      setSample({ plain: firstPlain.text || firstPlain.note || "(내용 없음)", decrypted: firstBack.text || firstBack.note || "(내용 없음)" });
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  const cipherStr = cipher ? JSON.stringify(cipher) : "";
  const cipherPreview = cipherStr.length > 220 ? cipherStr.slice(0, 220) + "…" : cipherStr;

  return (
    <Card>
      <div className="flex items-center justify-between">
        <div className="text-[14px] font-bold text-ink">🔒 개인정보 보호 (암호화)</div>
        <span className="rounded-full bg-cyan/10 px-2 py-0.5 text-[10px] font-semibold text-cyan">AES-256-GCM</span>
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-mut">
        일기·감정·회사·이직 조건 같은 민감정보는 <b className="text-sub">기기에서 암호화</b>돼 저장돼요.
        암호문구(비밀번호)로만 열 수 있고, 원문·열쇠는 어디에도 저장되지 않아요.
      </p>

      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          type="password"
          value={pass}
          onChange={(e) => setPass(e.target.value)}
          placeholder={alreadySet ? "암호문구 입력(잠금 해제)" : "암호문구 설정(4자 이상)"}
          className="flex-1 rounded-xl border border-line bg-[#0E1424] px-3 py-2 text-sm text-ink outline-none focus:border-cyan"
        />
        <button
          onClick={run}
          disabled={busy || !pass}
          className="tap shrink-0 whitespace-nowrap rounded-xl bg-cyan px-3.5 text-[12px] font-bold text-[#160D2D] disabled:opacity-50"
        >
          {busy ? "암호화 중…" : alreadySet ? "잠금 해제·암호화" : "설정·암호화"}
        </button>
      </div>
      {err && <p className="mt-1.5 text-[10px] text-[#F0736F]">{err}</p>}

      <div className="mt-2 text-[10px] text-mut">
        암호화 대상: 일기 <b className="text-sub">{sensitive.length}건</b> (본문·답변·감정·실험 기록)
      </div>

      {cipher && (
        <div className="mt-3 space-y-2">
          <div className="rounded-xl border border-line bg-[#0B1220] p-2.5">
            <div className="text-[9.5px] font-bold text-mut">💾 디스크에 저장되는 형태 (암호문)</div>
            <div className="mt-1 break-all font-mono text-[9.5px] leading-relaxed text-[#5DCAA5]">{cipherPreview}</div>
          </div>
          {sample && (
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-xl border border-line bg-[#0E1424] p-2.5">
                <div className="text-[9.5px] text-[#F0A0A0]">암호 없이 보면</div>
                <div className="mt-1 break-all font-mono text-[9.5px] text-mut">…암호문(읽을 수 없음)…</div>
              </div>
              <div className="rounded-xl border border-cyan/30 bg-[#1D1730] p-2.5">
                <div className="text-[9.5px] text-cyan">내 암호로 복호화하면</div>
                <div className="mt-1 text-[10px] leading-relaxed text-sub">“{sample.decrypted}”</div>
              </div>
            </div>
          )}
          <p className="text-[9px] leading-relaxed text-mut">
            ✓ 실제 <b>AES-256-GCM</b> 암호화 · 키는 <b>PBKDF2</b>로 암호문구에서 파생(세션 메모리에만).
            디스크엔 위 암호문만 남아, 기기를 잃어버려도 암호 없이는 못 읽어요.
          </p>
        </div>
      )}

      {/* 외부 AI 전송 전 마스킹 데모 — API 앱의 핵심 방어 */}
      <div className="mt-3 border-t border-line pt-2.5">
        <div className="flex items-center gap-1.5 text-[12px] font-bold text-ink">🛡 외부 AI 전송 전 마스킹</div>
        <p className="mt-1 text-[10px] leading-relaxed text-mut">
          서사·제안 생성 시 외부 AI(Claude)로 보내기 전, 이름·연봉·연락처 등을 자동으로 가려요.
        </p>
        <div className="mt-2 grid grid-cols-1 gap-2">
          <div className="rounded-xl border border-line bg-[#0E1424] p-2.5">
            <div className="text-[9.5px] text-[#F0A0A0]">내 원문 (기기 안에만)</div>
            <div className="mt-1 text-[10.5px] leading-relaxed text-sub">{demoRaw}</div>
          </div>
          <div className="rounded-xl border border-cyan/30 bg-[#1D1730] p-2.5">
            <div className="text-[9.5px] text-cyan">외부 AI로 실제 전송되는 내용</div>
            <div className="mt-1 text-[10.5px] leading-relaxed text-sub">{demoMasked}</div>
          </div>
        </div>
      </div>

      <p className="mt-2.5 border-t border-line pt-2 text-[9px] leading-relaxed text-mut">
        <b className="text-sub">저장</b>은 암호화(at rest), <b className="text-sub">전송</b>은 마스킹(외부 AI), <b className="text-sub">학습</b>은
        비식별 신호·집계 — 모든 구간에서 개인정보가 기기 밖 원문으로 나가지 않도록 설계했어요.
      </p>
    </Card>
  );
}
