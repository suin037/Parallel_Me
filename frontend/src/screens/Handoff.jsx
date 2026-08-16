import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import QRCode from "qrcode";
import { Check, Copy, Link2, Share2, Smartphone } from "lucide-react";
import { Eyebrow, Card, Caption } from "../components/ui.jsx";
import { buildResumeLink, collectState, describeState, packState, QR_MAX, LINK_WARN } from "../data/handoff.js";

// 기기 옮기기 (보내는 쪽) — 지금 기록을 링크 하나로 만든다.
//
// 방향에 따라 쓰는 수단이 다르다.
//  · 폰 → 노트북 : 노트북엔 카메라가 마땅치 않다. 링크를 나에게 보내고(카톡·메일)
//                  노트북에서 그 링크를 연다. 이게 이 화면의 주 용도.
//  · 노트북 → 폰 : QR 을 띄우고 폰으로 찍는다. 덤으로 같이 지원한다.
export default function Handoff() {
  const navigate = useNavigate();
  const [link, setLink] = useState("");
  const [qr, setQr] = useState("");
  const [summary, setSummary] = useState(null);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const state = collectState();
        if (!Object.keys(state).length) {
          if (alive) setErr("아직 옮길 기록이 없어요. 체험을 먼저 해보세요.");
          return;
        }
        const payload = await packState(state);
        const url = buildResumeLink(payload);
        if (!alive) return;
        setSummary({ ...describeState(state), size: payload.length });
        setLink(url);
        // QR 은 데이터가 작을 때만. 크면 칸이 촘촘해져 카메라가 못 읽는다.
        if (payload.length <= QR_MAX) {
          const dataUrl = await QRCode.toDataURL(url, {
            // 화면 크기(≈288px)보다 크게 그려서 축소해도 칸 경계가 뭉개지지 않게 한다.
            width: 640,
            margin: 1,
            errorCorrectionLevel: "L", // 담을 수 있는 양을 최대로 (화면 QR은 훼손 걱정이 없다)
            color: { dark: "#0B1220", light: "#FFFFFF" },
          });
          if (alive) setQr(dataUrl);
        }
      } catch (e) {
        if (alive) setErr(String(e?.message || e));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setErr("복사가 막혔어요. 아래 주소를 길게 눌러 직접 복사해 주세요.");
    }
  }

  async function share() {
    try {
      await navigator.share({ title: "이어서 하기", text: "다른 기기에서 이어서 체험하기", url: link });
    } catch {
      /* 사용자가 취소했거나 iframe 안이라 막힌 경우 — 복사 버튼이 대안이다 */
    }
  }

  return (
    <div className="pb-6">
      <div className="flex items-center justify-between">
        <Eyebrow>HANDOFF · 기기 옮기기</Eyebrow>
        <button onClick={() => navigate(-1)} className="tap text-[13px] text-sub">닫기</button>
      </div>
      <h1 className="mb-1 text-[22px] font-bold tracking-[-.025em]">다른 기기에서 이어서 하기</h1>
      <p className="mb-4 text-[11px] leading-relaxed text-mut">
        지금까지의 기록을 링크 하나에 담아요. 그 링크를 다른 기기에서 열면 그대로 이어집니다.
      </p>

      {err && (
        <Card>
          <p className="text-[12px] text-[#F0736F]">{err}</p>
        </Card>
      )}

      {summary && (
        <Card>
          <div className="text-xs font-semibold text-mut">옮겨지는 기록</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {summary.name && <Chip>{summary.name}</Chip>}
            <Chip>체크인 {summary.checkins}개</Chip>
            {summary.scenarios > 0 && <Chip>시나리오 {summary.scenarios}개</Chip>}
            {summary.universes > 0 && <Chip>저장한 평행우주 {summary.universes}개</Chip>}
            {summary.demo && <Chip>예시 1년치 포함</Chip>}
          </div>
          <Caption>
            설정·아바타·일기·펫까지 함께 옮겨져요. 링크 크기 {(summary.size / 1024).toFixed(1)}KB
            {summary.size > LINK_WARN && " · 주소가 길어 일부 앱에서 잘릴 수 있어요"}
          </Caption>
        </Card>
      )}

      {/* 폰 → 노트북 : 링크를 나에게 보내고 노트북에서 연다 */}
      {link && (
        <Card highlight>
          <div className="flex items-center gap-1.5 text-[13px] font-bold text-ink">
            <Link2 size={14} className="text-cyan" /> 링크로 보내기
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-mut">
            폰에서 노트북으로 옮길 때 이 방법을 쓰세요. 카톡 <b className="text-sub">나에게 보내기</b>나 메일로
            보낸 뒤, 노트북에서 그 링크를 열면 됩니다.
          </p>

          <div className="mt-3 grid grid-cols-2 gap-2">
            {typeof navigator !== "undefined" && navigator.share && (
              <button
                onClick={share}
                className="tap flex items-center justify-center gap-1.5 rounded-xl bg-cyan py-2.5 text-[12px] font-bold text-[#08131f]"
              >
                <Share2 size={14} /> 공유하기
              </button>
            )}
            <button
              onClick={copy}
              className={`tap flex items-center justify-center gap-1.5 rounded-xl border border-line bg-[#0E1424] py-2.5 text-[12px] font-bold ${
                copied ? "text-cyan" : "text-sub"
              } ${typeof navigator !== "undefined" && navigator.share ? "" : "col-span-2"}`}
            >
              {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "복사됐어요" : "링크 복사"}
            </button>
          </div>

          <div className="mt-2 max-h-16 overflow-y-auto break-all rounded-xl border border-line bg-[#0B1220] p-2 font-mono text-[9px] leading-relaxed text-mut">
            {link}
          </div>
        </Card>
      )}

      {/* 노트북 → 폰 : QR 이 제일 빠르다 */}
      {qr && (
        <Card>
          <div className="flex items-center gap-1.5 text-[13px] font-bold text-ink">
            <Smartphone size={14} className="text-cyan" /> QR로 폰에 옮기기
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-mut">
            노트북에서 폰으로 옮길 때는 이걸 카메라로 찍으세요.
          </p>
          <div className="mt-3 flex justify-center">
            <img
              src={qr}
              alt="이어서 하기 QR 코드"
              className="w-full max-w-[288px] rounded-2xl bg-white p-2.5"
            />
          </div>
        </Card>
      )}

      {link && !qr && !err && (
        <Card>
          <Caption className="mt-0">
            기록이 많아 QR로는 담기 어려워요. 위의 <b className="text-sub">링크 공유·복사</b>를 사용해 주세요.
          </Caption>
        </Card>
      )}

      <Card>
        <div className="text-[12px] font-bold text-ink">🔒 알아두실 점</div>
        <ul className="mt-1.5 space-y-1 text-[10.5px] leading-relaxed text-mut">
          <li>· 기록은 링크의 <b className="text-sub">#</b> 뒤에 담깁니다. 이 부분은 서버로 전송되지 않아 우리 서버에 아무 기록도 남지 않아요.</li>
          <li>· 대신 <b className="text-sub">링크 자체가 열쇠</b>입니다. 다른 사람에게 보내면 그 사람도 내 기록을 봅니다.</li>
          <li>· 메신저로 보내면 그 메신저에는 링크가 남아요. 신경 쓰인다면 옮긴 뒤 대화를 지워주세요.</li>
        </ul>
      </Card>
    </div>
  );
}

function Chip({ children }) {
  return (
    <span className="rounded-full border border-cyan/25 bg-cyan/10 px-2.5 py-1 text-[10px] font-semibold text-cyan">
      {children}
    </span>
  );
}
