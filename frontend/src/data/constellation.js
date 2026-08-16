// 일기 entries → 주별 별자리. 각 일기 = 별 하나(v=기분 1~5).
// 주마다 기분 시퀀스가 달라 별자리 '모양'이 바뀐다. 리포트도 주 단위로 묶는다.

function isoWeekStart(dateStr) {
  const d = new Date(dateStr);
  const dow = (d.getDay() + 6) % 7; // 월요일=0
  d.setDate(d.getDate() - dow);
  return d.toISOString().slice(0, 10);
}

function weekLabel(weekStart) {
  const thisWeek = isoWeekStart(new Date().toISOString().slice(0, 10));
  const diffWeeks = Math.round((new Date(thisWeek) - new Date(weekStart)) / (7 * 86400000));
  if (diffWeeks === 0) return "이번 주";
  if (diffWeeks === 1) return "지난 주";
  const [, m, d] = weekStart.split("-");
  return `${Number(m)}.${Number(d)} 주`;
}

// 기분 시퀀스 → 별자리 이름(모양 성격). 가벼운 재미 라벨.
function shapeName(stars) {
  if (!stars.length) return "빈 하늘";
  const vals = stars.map((s) => s.v);
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  const rising = vals[vals.length - 1] - vals[0];
  const range = Math.max(...vals) - Math.min(...vals);
  if (range >= 3) return "요동치는 별자리";
  if (rising >= 2) return "떠오르는 별자리";
  if (rising <= -2) return "저무는 별자리";
  if (avg >= 4) return "환한 별자리";
  if (avg <= 2) return "웅크린 별자리";
  return "잔잔한 별자리";
}

// 달력주(월~일) 기준. 각 주 = 7개 요일 슬롯. 기록한 날만 '별'(filled), 안 한 날은 빈 자리.
// weeksAgo: 0=이번 주, 1=지난 주 …
function weekdayIdx(dateStr) {
  return (new Date(dateStr).getDay() + 6) % 7; // 월=0 … 일=6
}
export const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];

export function weeklyConstellations(entries) {
  const byWeek = {};
  for (const e of entries) {
    const ws = isoWeekStart(e.date);
    (byWeek[ws] ||= {})[weekdayIdx(e.date)] = e;
  }
  const thisWs = isoWeekStart(new Date().toISOString().slice(0, 10));
  const starts = Object.keys(byWeek).sort(); // 오래된 → 최근

  const weeks = starts.map((ws) => {
    // 7개 슬롯(월~일). 기록 있으면 별, 없으면 빈 자리.
    const slots = WEEKDAYS.map((wd, d) => {
      const e = byWeek[ws][d];
      return e
        ? { weekday: wd, filled: true, v: e.mood, text: e.text, date: e.date, answers: e.answers || null }
        : { weekday: wd, filled: false };
    });
    const recorded = slots.filter((s) => s.filled);
    const weeksAgo = Math.round((new Date(thisWs) - new Date(ws)) / (7 * 86400000));
    const n = recorded.length;
    const avg = n ? recorded.reduce((a, s) => a + s.v, 0) / n : 0;
    const best = n ? recorded.reduce((a, b) => (b.v >= a.v ? b : a)) : null;
    const worst = n ? recorded.reduce((a, b) => (b.v <= a.v ? b : a)) : null;
    return {
      weekStart: ws, weeksAgo,
      label: weeksAgo === 0 ? "이번 주" : weeksAgo === 1 ? "지난 주" : `${weeksAgo}주 전`,
      shape: shapeName(recorded),
      slots,            // 7개(요일) — filled/empty
      stars: recorded,  // 실제 기록만(분석·통계용)
      n, avg: +avg.toFixed(1), best, worst,
      detailed: recorded.filter((s) => s.answers).length,
    };
  });
  return weeks; // 오래된 → 최근 (기본 선택은 마지막=이번 주)
}
