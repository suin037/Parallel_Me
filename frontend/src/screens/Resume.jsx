import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Download } from "lucide-react";
import { Eyebrow, Card, Caption, Button } from "../components/ui.jsx";
import { applyState, clearIncoming, collectState, describeState, readIncoming, unpackState } from "../data/handoff.js";

// 기기 옮기기 (받는 쪽) — 다른 기기에서 만든 링크로 들어오는 자리.
//
// 바로 심지 않고 한 번 확인을 받는다. 이 기기에 이미 기록이 있으면 덮어쓰기가
// 되기 때문이다(전시장 공용 노트북에서 남의 기록을 날리는 사고 방지).
export default function Resume() {
  const navigate = useNavigate();
  const [incoming, setIncoming] = useState(null); // { summary, state, at }
  const [existing, setExisting] = useState(null); // 이 기기에 이미 있는 기록
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      const payload = readIncoming();
      if (!payload) {
        if (alive) setErr("이어받을 데이터가 링크에 없어요. 보낸 기기에서 링크를 다시 만들어 주세요.");
        return;
      }
      try {
        const { state, at } = await unpackState(payload);
        if (!alive) return;
        setIncoming({ state, at, summary: describeState(state) });
        const mine = collectState();
        if (Object.keys(mine).length) setExisting(describeState(mine));
      } catch {
        if (alive) setErr("링크가 손상됐어요. 주소가 중간에 잘렸을 수 있어요 — 다시 보내주세요.");
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  function restore() {
    if (!incoming) return;
    setBusy(true);
    applyState(incoming.state);
    clearIncoming(); // 주소창에서 데이터 제거 — 뒤로가기·재공유로 새어나가지 않게
    // 컨텍스트들은 처음 뜰 때 localStorage 를 읽는다. 이미 떠 있는 상태에서
    // 값만 바꾸면 화면이 옛 데이터를 들고 있으므로 통째로 다시 띄운다.
    window.location.replace("/my");
  }

  return (
    <div className="pb-6">
      <Eyebrow>RESUME · 이어서 하기</Eyebrow>
      <h1 className="mb-1 text-[22px] font-bold tracking-[-.025em]">다른 기기의 기록을 불러올까요?</h1>
      <p className="mb-4 text-[11px] leading-relaxed text-mut">
        이 기기에 기록을 심으면 바로 이어서 체험할 수 있어요.
      </p>

      {err && (
        <>
          <Card>
            <p className="text-[12px] leading-relaxed text-[#F0736F]">{err}</p>
          </Card>
          <Button variant="ghost" onClick={() => navigate("/")}>처음 화면으로</Button>
        </>
      )}

      {incoming && (
        <>
          <Card highlight>
            <div className="text-xs font-semibold text-mut">불러올 기록</div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {incoming.summary.name && <Chip>{incoming.summary.name}</Chip>}
              <Chip>체크인 {incoming.summary.checkins}개</Chip>
              {incoming.summary.scenarios > 0 && <Chip>시나리오 {incoming.summary.scenarios}개</Chip>}
              {incoming.summary.universes > 0 && <Chip>저장한 평행우주 {incoming.summary.universes}개</Chip>}
              {incoming.summary.demo && <Chip>예시 1년치 포함</Chip>}
            </div>
            {incoming.at && (
              <Caption>{new Date(incoming.at).toLocaleString("ko-KR")}에 만들어진 링크예요.</Caption>
            )}
          </Card>

          {existing && (
            <Card>
              <div className="flex items-start gap-2">
                <AlertTriangle size={15} className="mt-0.5 shrink-0 text-[#F0A0A0]" />
                <div>
                  <div className="text-[12px] font-bold text-ink">이 기기에도 기록이 있어요</div>
                  <p className="mt-1 text-[10.5px] leading-relaxed text-mut">
                    체크인 {existing.checkins}개{existing.name && ` · ${existing.name}`} — 불러오면{" "}
                    <b className="text-[#F0A0A0]">겹치는 기록은 덮어써집니다.</b> 되돌릴 수 없어요.
                  </p>
                </div>
              </div>
            </Card>
          )}

          <div className="mt-3 space-y-2">
            <Button onClick={restore}>
              <span className="inline-flex items-center gap-1.5">
                <Download size={15} /> {busy ? "불러오는 중…" : "이 기기로 불러오기"}
              </span>
            </Button>
            <Button variant="ghost" onClick={() => navigate("/")}>
              불러오지 않고 처음부터 하기
            </Button>
          </div>

          <Caption>
            이 링크의 기록은 서버를 거치지 않고 주소에 담겨 바로 전달됐어요.
          </Caption>
        </>
      )}
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
