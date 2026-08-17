import { useMemo, useState } from "react";
import { ChevronRight, EyeOff, KeyRound, ShieldCheck, TriangleAlert } from "lucide-react";
import { Card } from "./ui.jsx";
import { loadUniverse } from "../data/myUniverse.js";
import { useResult } from "../data/ResultContext.jsx";
import { redactPII } from "../data/piiRedact.js";
import { isPersistent, storageNote } from "../data/safeStorage.js";
import { hasCrypto, isPassphraseSet, setupPassphrase, unlock, encryptJSON, decryptJSON } from "../data/secureStore.js";

// ─────────────────────────────────────────────────────────────
// 개인정보 · 보안 — "내 기록이 지금 어디에 어떤 형태로 있는가" 를 사실대로 보여주는 화면.
//
// 이 화면의 규칙: **하지 않는 일을 한다고 적지 않는다.**
//   전에는 "민감정보는 기기에서 암호화돼 저장돼요" 라고 적혀 있었는데, 실제로는
//   그렇지 않다. secureStore 는 진짜 암호화 모듈이지만(PBKDF2 210k + AES-256-GCM)
//   앱의 저장 경로(myUniverse → safeStorage → localStorage)에 연결돼 있지 않고,
//   아래 '암호화 확인' 버튼이 그 자리에서 암호문을 만들어 보여준 뒤 버린다.
//   저장된 일기는 계속 평문이다. 그래서 문구를 사실에 맞췄고, 무엇이 아직
//   안 되어 있는지도 같은 크기로 적는다 — 보안 화면에서 과장은 그 자체가 위험이다.
//
// 마스킹은 반대로 **진짜 동작한다.** 다만 전부가 아니라 두 경로다
//   (RelationshipInput 의 대화 전문, Result 의 비교 선택지 두 줄).
//   그래서 "다 가려요" 가 아니라 어디에 걸려 있는지를 적는다.
// ─────────────────────────────────────────────────────────────

function Row({ icon: Icon, label, value, tone = "mut", note }) {
  const color = tone === "warn" ? "text-[#E8B36B]" : tone === "ok" ? "text-violet-200" : "text-sub";
  return (
    <div className="flex items-start gap-2.5 border-t border-white/[.06] py-2.5 first:border-t-0 first:pt-0">
      <Icon size={13} className="mt-[2px] shrink-0 text-mut" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-2">
          <span className="text-[11px] text-sub">{label}</span>
          <span className={`text-[11px] font-semibold ${color}`}>{value}</span>
        </div>
        {note && <p className="mt-1 text-[9.5px] leading-relaxed text-mut">{note}</p>}
      </div>
    </div>
  );
}

export default function PrivacyVault() {
  const { profile } = useResult();
  const [pass, setPass] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [cipher, setCipher] = useState(null);
  const [sample, setSample] = useState(null);
  const [open, setOpen] = useState(false);
  const locked = useMemo(() => isPassphraseSet(), []);

  // 암호화 대상이 될 기록 — 지금은 '몇 건인지' 를 세는 용도다(아직 저장을 잠그지는 않는다).
  const sensitive = useMemo(() => {
    const u = loadUniverse();
    return (u.checkins || [])
      .filter((c) => !c.empty)
      .map((c) => ({ date: c.date, text: c.text, note: c.note, answers: c.answers, emotion: c.emotion, experiments: c.experiments }));
  }, []);

  // 마스킹 시연 — 이름만 실제 프로필에서 가져온다(나머지는 예시 값).
  const name = profile?.name?.trim() || "김지원";
  const demoRaw = `저는 ${name}입니다. 지금 연봉 4200만원인데 이직 고민 중. 연락처 010-1234-5678`;
  const demoMasked = redactPII(demoRaw, { name, company: "" }).masked;

  async function run() {
    if (!hasCrypto()) { setErr("이 브라우저는 Web Crypto 를 지원하지 않아요."); return; }
    if (pass.length < 4) { setErr("암호문구는 4자 이상으로 적어 주세요."); return; }
    setBusy(true); setErr(null);
    try {
      const key = locked ? await unlock(pass) : await setupPassphrase(pass);
      if (!key) { setErr("암호문구가 맞지 않아요."); setBusy(false); return; }
      const blob = await encryptJSON(sensitive, key);
      setCipher(blob);
      const back = await decryptJSON(blob, key);
      const first = sensitive.find((x) => x.text) || sensitive[0] || {};
      const backFirst = (back || []).find((x) => x.date === first.date) || {};
      setSample({ decrypted: backFirst.text || backFirst.note || "(내용 없음)" });
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }

  const cipherStr = cipher ? JSON.stringify(cipher) : "";
  const cipherPreview = cipherStr.length > 200 ? `${cipherStr.slice(0, 200)}…` : cipherStr;
  const note = storageNote();

  return (
    <Card>
      <div className="flex items-center gap-2">
        <ShieldCheck size={16} className="text-violet-300" />
        <h2 className="text-[14px] font-bold tracking-[-.02em] text-ink">개인정보 · 보안</h2>
      </div>
      <p className="mt-1.5 text-[11px] leading-relaxed text-sub">
        내 기록이 지금 어디에 어떤 형태로 있는지, 밖으로 나갈 때 무엇이 가려지는지 그대로 적었어요.
      </p>

      {/* ── 지금 상태 ─────────────────────────────────────── */}
      <div className="mt-4 rounded-[16px] border border-white/[.07] bg-black/20 px-3.5 py-3">
        <p className="text-[10px] font-semibold uppercase tracking-[.12em] text-mut">지금 이 기기</p>
        <div className="mt-2">
          <Row
            icon={KeyRound}
            label="일기·프로필 저장 형태"
            value="평문"
            tone="warn"
            note={`이 브라우저 저장소에 그대로 들어 있어요(기록 ${sensitive.length}건). 아직 잠겨 있지 않습니다.`}
          />
          <Row
            icon={ShieldCheck}
            label="저장 위치"
            value={isPersistent ? "이 브라우저 안" : "메모리(임시)"}
            tone={isPersistent ? "ok" : "warn"}
            note={note || "서버에 올리지 않아요. 기기를 바꾸면 따라가지 않습니다."}
          />
          <Row
            icon={EyeOff}
            label="외부 AI 전송 시 가리기"
            value="켜짐 (일부)"
            tone="ok"
            note="관계 상담에 넣는 대화 전문과, 비교에 올리는 두 선택지 문장에 걸려 있어요. 그 밖의 요청은 아직 거치지 않습니다."
          />
        </div>
      </div>

      {/* ── 마스킹 — 실제로 동작하는 부분이라 먼저 둔다 ────── */}
      <div className="mt-4">
        <div className="flex items-center gap-1.5">
          <EyeOff size={13} className="text-violet-300" />
          <h3 className="text-[12px] font-bold text-ink">외부 AI로 나가기 전에 가려요</h3>
        </div>
        <p className="mt-1 text-[10px] leading-relaxed text-mut">
          서사·제안을 만들 때 외부 AI 로 보내기 전, 이름·금액·연락처를 자동으로 바꿔요.
        </p>
        <div className="mt-2.5 space-y-1.5">
          <div className="rounded-[14px] border border-white/[.07] bg-black/20 px-3 py-2.5">
            <p className="text-[9px] font-semibold text-mut">내가 적은 것 — 기기 안에만</p>
            <p className="mt-1 text-[10.5px] leading-relaxed text-sub">{demoRaw}</p>
          </div>
          <div className="rounded-[14px] border border-violet-400/25 bg-violet-500/[.08] px-3 py-2.5">
            <p className="text-[9px] font-semibold text-violet-200">실제로 나가는 것</p>
            <p className="mt-1 text-[10.5px] leading-relaxed text-sub">{demoMasked}</p>
          </div>
        </div>
      </div>

      {/* ── 암호화 — 시연이라는 걸 제목에서부터 밝힌다 ────── */}
      <div className="mt-4 overflow-hidden rounded-[16px] border border-white/[.07] bg-black/15">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="tap flex w-full items-center justify-between gap-3 px-3.5 py-3 text-left"
        >
          <span className="min-w-0">
            <span className="flex items-center gap-1.5 text-[12px] font-bold text-ink">
              <KeyRound size={13} className="text-violet-300" /> 암호화 방식 확인해 보기
            </span>
            <span className="mt-1 block text-[9.5px] leading-relaxed text-mut">
              암호문구로 잠그면 어떤 모습이 되는지 이 자리에서 직접 만들어 봐요
            </span>
          </span>
          <ChevronRight size={14} className={`shrink-0 text-mut transition-transform ${open ? "rotate-90" : ""}`} />
        </button>

        {open && (
          <div className="border-t border-white/[.06] px-3.5 pb-3.5 pt-3">
            {/* 이 자리에서 가장 중요한 한 줄 — 눌러도 저장이 잠기지는 않는다. */}
            <div className="flex items-start gap-2 rounded-xl border border-[#E8B36B]/25 bg-[#E8B36B]/[.08] px-3 py-2.5">
              <TriangleAlert size={13} className="mt-[1px] shrink-0 text-[#E8B36B]" />
              <p className="text-[9.5px] leading-relaxed text-[#E7D3B4]">
                이건 <b>확인용</b>이에요. 여기서 만든 암호문은 화면에만 보이고 저장되지 않으며, 저장된 일기는
                그대로 평문으로 남습니다.
              </p>
            </div>

            <div className="mt-2.5 flex flex-col gap-2 sm:flex-row">
              <input
                type="password"
                value={pass}
                onChange={(e) => setPass(e.target.value)}
                placeholder={locked ? "암호문구 입력" : "암호문구 설정 (4자 이상)"}
                className="flex-1 rounded-xl border border-white/12 bg-[#0E1424] px-3 py-2.5 text-[12px] text-ink outline-none transition-colors placeholder:text-mut focus:border-violet-400/60"
              />
              <button
                type="button"
                onClick={run}
                disabled={busy || !pass}
                className="tap shrink-0 whitespace-nowrap rounded-xl bg-[#8B6CCF] px-4 py-2.5 text-[12px] font-bold text-white disabled:opacity-40"
              >
                {busy ? "암호화 중…" : "암호화해 보기"}
              </button>
            </div>
            {err && <p className="mt-1.5 text-[10px] text-[#F0736F]">{err}</p>}

            {cipher && (
              <div className="mt-3 space-y-1.5">
                <div className="rounded-[14px] border border-white/[.07] bg-black/25 px-3 py-2.5">
                  <p className="text-[9px] font-semibold text-mut">잠갔을 때의 모습</p>
                  <p className="mt-1 break-all font-mono text-[9.5px] leading-relaxed text-violet-200/80">{cipherPreview}</p>
                </div>
                {sample && (
                  <div className="rounded-[14px] border border-violet-400/25 bg-violet-500/[.08] px-3 py-2.5">
                    <p className="text-[9px] font-semibold text-violet-200">내 암호문구로 다시 열면</p>
                    <p className="mt-1 text-[10.5px] leading-relaxed text-sub">“{sample.decrypted}”</p>
                  </div>
                )}
                <p className="text-[9px] leading-relaxed text-mut">
                  AES-256-GCM · 키는 PBKDF2(SHA-256, 210,000회)로 암호문구에서 만들고 세션 메모리에만 둡니다.
                  암호문구 자체는 어디에도 저장되지 않아요.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      <p className="mt-3.5 border-t border-white/[.07] pt-2.5 text-[9px] leading-relaxed text-mut">
        기록은 이 기기에만 두고, 밖으로 보낼 때는 위에 적은 두 경로에서 개인정보를 가립니다.
        저장 자체를 암호로 잠그는 건 아직 준비 중이라, 지금 상태를 위에 그대로 적어 뒀어요.
      </p>
    </Card>
  );
}
