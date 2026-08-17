import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import Constellation, { MoodLegend } from "./Constellation.jsx";
import JyConstellationArchive from "./JyConstellationArchive.jsx";
import { constellationGroups, loadUniverse, todayKey } from "../data/myUniverse.js";
import { zodiacOf } from "../data/zodiac.js";
import { classifyConstellation, badgeLabel, HONESTY_NOTE } from "../data/constellationRules.js";
import { useResult } from "../data/ResultContext.jsx";
import { MOOD_COLORS } from "../data/moodColors.js";

export default function HomeCalendar() {
  // 가치 순위로 별자리 주제(성장/안정/관계…)를 정한다 — 이름의 뒷말이 된다.
  const { profile } = useResult();
  const state = loadUniverse();
  const entries = useMemo(() => (state.checkins || []).filter((entry) => !entry.empty && entry.date), [state]);
  const years = useMemo(() => [...new Set(entries.map((entry) => Number(entry.date.slice(0, 4))))].sort((a,b)=>b-a), [entries]);
  const fallbackYear = new Date().getFullYear();
  const [year,setYear] = useState(years[0] || fallbackYear);
  const [month,setMonth] = useState(null);
  const [week,setWeek] = useState(null);
  const [star,setStar] = useState(null);
  const [report,setReport] = useState(null);
  // 주간 별자리는 '달력 한 주(7일)' 기준이어야 한다 — adaptiveGroups(기록 수에 맞춘 큰 묶음)를
  // 쓰면 한 묶음이 32일이 되어 라벨·모양·리포트가 모두 깨진다.
  const groups = useMemo(() => constellationGroups(state),[state]);
  const months = useMemo(() => Array.from({length:12},(_,index)=>{
    const key=`${year}-${String(index+1).padStart(2,"0")}`;
    const items=entries.filter((entry)=>entry.date.startsWith(key));
    const moods=items.map((entry)=>entry.mood).filter(Boolean);
    return {key,index:index+1,items,count:items.length,avg:moods.length?moods.reduce((a,b)=>a+b,0)/moods.length:null};
  }),[entries,year]);
  const monthWeeks = useMemo(() => month ? groups.filter((group)=>group.stars.some((item)=>!item.empty&&item.date?.startsWith(month))) : [],[groups,month]);
  // 12달을 전부 넘긴다 — 기록이 없는 달도 별자리 밑그림은 깔리고, 기록한 달만 밝아진다.
  // (예전엔 기록 있는 달만 넘겨서 빈 달이 아예 안 보였다.)
  const allMonthGroups=useMemo(()=>months.map((item)=>({monthKey:item.key,entries:item.items,n:item.count,avgMood:item.avg})),[months]);
  // 달 경계를 넘는 주(예: 12.29~1.4)는 양쪽 달 모두에 걸린다. 그대로 두면 그 주의 별이
  // 두 달에서 각각 세어져 별 개수가 실제 기록보다 부풀었다. 달별로는 그 달 날짜만 채운
  // 것으로 가리고(칸 7개는 유지 — 레이아웃이 흔들리지 않게), 주간 리포트를 열 때는
  // full 로 원래 한 주를 그대로 넘긴다.
  const weeksByMonth=useMemo(()=>Object.fromEntries(allMonthGroups.map((item)=>[item.monthKey,
    groups.filter((group)=>group.stars.some((star)=>!star.empty&&star.date?.startsWith(item.monthKey)))
      .map((group)=>({...group,full:group,
        stars:group.stars.map((star)=>star.date?.startsWith(item.monthKey)?star:{...star,empty:true}),
      }))])),[allMonthGroups,groups]);

  // 기록이 있는 달 전체(연도 넘어서까지) — 상단 화살표로 한 달씩 넘길 때 쓴다.
  const allMonths = useMemo(()=>[...new Set(entries.map((entry)=>entry.date.slice(0,7)))].sort(),[entries]);

  function moveYear(delta) { setYear((value)=>value+delta); setMonth(null); setWeek(null); setStar(null); }
  // 달을 고른 상태면 ‹ ›가 한 달씩(연도 경계도 넘어) 이동, 아니면 연도 이동.
  function step(delta) {
    if (!month) { moveYear(delta); return; }
    const at = allMonths.indexOf(month);
    const next = allMonths[at + delta];
    if (!next) return;
    setMonth(next);
    setYear(Number(next.slice(0, 4)));
    setWeek(null);
    setStar(null);
  }
  const atFirst = month ? allMonths.indexOf(month) <= 0 : false;
  const atLast = month ? allMonths.indexOf(month) >= allMonths.length - 1 : false;

  return <section className="mt-5 rounded-[24px] border border-white/[.08] bg-[#0B1322] p-4 lg:p-5">
    <div className="flex items-center justify-between gap-3"><div><p className="text-[10px] tracking-[.15em] text-[#9F85DD]">CONSTELLATION ARCHIVE</p><h2 className="mt-1 text-[17px] font-bold">나의 기록 별자리</h2></div>{/* 넘김 버튼은 아래 제목 줄에 붙였다 — 여기 두면 모달 닫기(×) 버튼과 겹친다. */}</div>
    {/* 월 선택 — 성단을 정확히 누르지 않아도 달을 고를 수 있게(리포트까지 닿는 길). */}
    <div className="mt-3 flex flex-wrap gap-1">
      {months.map((item)=>{
        const on=month===item.key, has=item.count>0;
        return <button key={item.key} disabled={!has} onClick={()=>{setMonth(on?null:item.key);setWeek(null);setStar(null);}}
          className={`tap rounded-full border px-2.5 py-1 text-[10px] transition-colors ${on?"border-[#8B6CCF] bg-[#8B6CCF]/20 text-[#C7B5F2]":has?"border-white/10 text-sub hover:border-[#8B6CCF]/50":"border-white/5 text-mut opacity-40"}`}>
          {item.index}월 <span className="text-[8px] text-mut">{zodiacOf(item.index).ko}</span>
        </button>;
      })}
    </div>
    <p className="mt-2.5 text-[10px] leading-relaxed text-mut">달마다 그 달의 별자리(황도 12궁) 모양으로 기록이 모입니다. 달을 고르면 같은 별들이 그달의 주간 별자리로 펼쳐집니다.</p>
    {/* 연·월 제목 + 넘김 — 큰 글씨 옆에 화살표를 붙여 한 손으로 오갈 수 있게. */}
    <div className="mt-3 flex items-center justify-center gap-2">
      <button onClick={()=>step(-1)} disabled={atFirst}
        className="tap flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/10 disabled:opacity-25"
        aria-label={month?"이전 달":"이전 해"}><ChevronLeft size={16}/></button>
      <div className="min-w-[150px] text-center">
        <div className="text-[17px] font-bold leading-tight text-ink">
          {year}년{month?` ${Number(month.slice(5))}월`:""}
          {month&&<span className="text-[#C7B5F2]"> · {zodiacOf(Number(month.slice(5))).ko}</span>}
        </div>
      </div>
      <button onClick={()=>step(1)} disabled={atLast}
        className="tap flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/10 disabled:opacity-25"
        aria-label={month?"다음 달":"다음 해"}><ChevronRight size={16}/></button>
    </div>

    <div className="mt-3"><JyConstellationArchive monthGroups={allMonthGroups} weeksByMonth={weeksByMonth} focusMonth={month} onMonthPick={(key)=>{setMonth(key);setWeek(null);setStar(null);}} onWeekOpen={(group)=>{setWeek(group.full||group);setStar(null);}}/></div>
    {month && <>
      <div className="mt-4 flex items-center justify-between rounded-xl border border-[#8B6CCF]/20 bg-[#8B6CCF]/[.07] px-3 py-2.5"><div><b className="text-[12px] text-[#C7B5F2]">{Number(month.slice(5))}월 · {zodiacOf(Number(month.slice(5))).ko}</b><p className="mt-0.5 text-[9px] text-mut">{months.find((item)=>item.key===month)?.count || 0}일 기록</p></div><button onClick={()=>{setMonth(null);setWeek(null);setStar(null);}} className="tap text-[10px] text-sub">12개월 보기</button></div>
      {/* 주 선택 — 별을 정확히 못 눌러도 주간 별자리·리포트로 갈 수 있게. */}
      {monthWeeks.length>0&&<div className="mt-2 flex flex-wrap gap-1">
        {monthWeeks.map((group)=>{
          const on=week?.weekStart===group.weekStart, days=group.stars.filter((item)=>!item.empty).length;
          return <button key={group.weekStart} onClick={()=>{setWeek(on?null:group);setStar(null);}}
            className={`tap rounded-lg border px-2 py-1 text-[10px] transition-colors ${on?"border-[#8B6CCF] bg-[#8B6CCF]/20 text-[#C7B5F2]":"border-white/10 text-sub hover:border-[#8B6CCF]/50"}`}>
            {shortDate(group.weekStart)}~ <span className="text-[8px] text-mut">{days}일</span>
          </button>;
        })}
      </div>}
      {week&&<div className="mt-3 rounded-[18px] border border-white/[.07] bg-black/15 p-4"><div className="flex items-center justify-between"><div><p className="text-[9px] text-[#A88BE8]">WEEK CONSTELLATION</p><b className="text-[12px]">{badgeLabel(classifyConstellation(week, profile?.value_ranking))}</b><p className="mt-0.5 text-[10px] text-sub">{classifyConstellation(week, profile?.value_ranking).caption}</p></div><button onClick={()=>setReport(week)} className="tap rounded-full bg-[#8B6CCF] px-3 py-1.5 text-[10px] font-bold">주간 리포트</button></div><div className="mx-auto mt-2 max-w-[330px]"><Constellation size={230} stars={week.stars} todayDate={todayKey()} selectedDate={star?.date} onSelect={setStar}/><MoodLegend className="mt-1.5 justify-center"/></div>{star&&<div className="mt-3 rounded-xl bg-white/[.035] p-3"><div className="flex justify-between text-[10px]"><b>{star.date}</b><span className="text-[#BBA4ED]">기분 {star.mood || "-"}/5</span></div><p className="mt-2 text-[11px] leading-relaxed text-sub">{star.text||star.note||"간단한 체크인만 남긴 날입니다."}</p></div>}</div>}
    </>}
    {report&&<WeeklyReport group={report} onClose={()=>setReport(null)}/>} 
  </section>;
}

function MonthCluster({item,onClick}) {
  const dots=Math.min(15,Math.max(5,item.count));
  return <button disabled={!item.count} onClick={onClick} className="tap w-full text-center disabled:opacity-25"><svg viewBox="0 0 100 72" className="h-[58px] w-full overflow-visible">{Array.from({length:dots},(_,i)=>{const angle=i*2.399;const radius=7+Math.sqrt(i)*7;const x=50+Math.cos(angle)*radius,y=36+Math.sin(angle)*radius*.68;const warm=item.avg!=null&&item.avg<3;return <g key={i}><circle cx={x} cy={y} r={8} fill={warm?"#D7774F":"#62CDBC"} opacity=".09"/><circle cx={x} cy={y} r={item.count>15?3.8:3} fill={warm?"#F0A45E":"#A6E2D8"} opacity={.68+(i/dots)*.28}/></g>;})}</svg><div className="-mt-1 text-[10px] font-semibold text-sub">{item.index}월 <span className="text-[8px] text-mut">{item.count}일</span></div></button>;
}

const MOOD_COL=MOOD_COLORS;   // 별자리와 같은 램프 — data/moodColors.js
const DAY_KO=["월","화","수","목","금","토","일"];

// 주간 리포트 — 숫자 나열 대신 '그 주가 어떻게 흘렀는지'가 한눈에 보이게.
function WeeklyReport({group,onClose}) {
  const { profile } = useResult();
  const cls=classifyConstellation(group, profile?.value_ranking);
  const filled=group.stars.filter((item)=>!item.empty);
  const moods=filled.map((item)=>item.mood).filter(Boolean);
  const avg=moods.length?(moods.reduce((a,b)=>a+b,0)/moods.length):null;
  const keywords=[...new Set(filled.map((item)=>item.keyword||item.emotion).filter(Boolean))].slice(0,6);
  // 전반 대비 후반 — 그 주가 나아졌는지 가라앉았는지.
  const half=Math.floor(moods.length/2);
  const trend=moods.length>=4
    ? (moods.slice(half).reduce((a,b)=>a+b,0)/(moods.length-half))-(moods.slice(0,half).reduce((a,b)=>a+b,0)/half)
    : null;
  const trendTxt=trend==null?null:trend>0.3?"뒤로 갈수록 나아진 주":trend<-0.3?"뒤로 갈수록 가라앉은 주":"큰 기복 없이 고른 주";
  const best=filled.filter((s)=>s.mood).sort((a,b)=>b.mood-a.mood)[0];
  const hard=filled.filter((s)=>s.mood).sort((a,b)=>a.mood-b.mood)[0];

  return (
    <div className="fixed inset-0 z-[100] flex items-end justify-center bg-[#02040B]/75 p-4 backdrop-blur-sm md:items-center" onClick={onClose}>
      <div className="max-h-[88dvh] w-full max-w-[560px] overflow-y-auto rounded-[26px] border border-white/10 bg-[#0C1424] p-5 shadow-[0_24px_70px_rgba(0,0,0,.5)]" onClick={(event)=>event.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] tracking-[.14em] text-[#A88BE8]">WEEKLY REPORT</p>
            <h3 className="mt-1 text-[19px] font-bold leading-tight">{shortDate(group.weekStart)} ~ {shortDate(group.weekEnd)}</h3>
            <p className="mt-1 text-[12px] font-semibold text-[#BBA4ED]">{cls.name}</p>
            <p className="mt-0.5 text-[11px] text-sub">{cls.caption}</p>
            {trendTxt&&<p className="mt-1 text-[11px] text-[#C7B5F2]">{trendTxt}</p>}
          </div>
          <button onClick={onClose} className="tap flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/[.07] text-sub"><X size={17}/></button>
        </div>

        {/* 7일 흐름 — 요일별 막대. 색=기분, 빈 날은 점선. */}
        <div className="mt-4 flex items-end gap-1.5">
          {group.stars.map((s,i)=>{
            const m=s.empty?null:s.mood;
            return (
              <div key={i} className="flex flex-1 flex-col items-center gap-1">
                <div className="flex h-[54px] w-full items-end">
                  {m ? (
                    <div className="w-full rounded-t-[4px]" style={{height:`${(m/5)*100}%`,background:MOOD_COL[m-1],opacity:.85}}/>
                  ) : (
                    <div className="h-[6px] w-full rounded border border-dashed border-white/15"/>
                  )}
                </div>
                <span className={`text-[9px] ${m?"text-sub":"text-mut"}`}>{DAY_KO[i]}</span>
              </div>
            );
          })}
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          {[["기록한 날",`${filled.length}일`],["기분 평균",avg?avg.toFixed(1):"—"],["감정 키워드",`${keywords.length}개`]].map(([label,value])=>(
            <div key={label} className="rounded-xl bg-white/[.04] p-3 text-center">
              <b className="text-[17px] text-[#BBA4ED]">{value}</b>
              <p className="mt-0.5 text-[9px] text-mut">{label}</p>
            </div>
          ))}
        </div>

        {keywords.length>0&&(
          <div className="mt-3 flex flex-wrap gap-1.5">
            {keywords.map((k)=>(
              <span key={k} className="rounded-full border border-[#8B6CCF]/30 bg-[#8B6CCF]/[.1] px-2.5 py-1 text-[10px] text-[#C7B5F2]">{k}</span>
            ))}
          </div>
        )}

        {/* 그 주의 양 끝 — 실제 그날 기록 한 줄씩. 숫자보다 이게 기억을 되살린다. */}
        <div className="mt-3 space-y-2">
          {best&&(best.text||best.note)&&(
            <div className="rounded-xl border border-[#5DCAA5]/20 bg-[#5DCAA5]/[.06] px-3 py-2.5">
              <p className="text-[9.5px] text-[#5DCAA5]">가장 좋았던 날 · {shortDate(best.date)}</p>
              <p className="mt-1 text-[11.5px] leading-relaxed text-sub">“{best.text||best.note}”</p>
            </div>
          )}
          {hard&&hard.date!==best?.date&&(hard.text||hard.note)&&(
            <div className="rounded-xl border border-[#F0736F]/20 bg-[#F0736F]/[.06] px-3 py-2.5">
              <p className="text-[9.5px] text-[#F0736F]">가장 힘들었던 날 · {shortDate(hard.date)}</p>
              <p className="mt-1 text-[11.5px] leading-relaxed text-sub">“{hard.text||hard.note}”</p>
            </div>
          )}
        </div>

        {filled.length===0&&<p className="mt-4 text-center text-[12px] text-mut">이 주에는 기록이 없습니다.</p>}
        {/* 이름을 붙이는 순간 '당신은 ○○형' 으로 읽힐 수 있어 고지를 함께 둔다. */}
        <p className="mt-4 text-[9px] leading-relaxed text-mut">{HONESTY_NOTE}</p>
      </div>
    </div>
  );
}

function shortDate(value) { const parts=String(value||"").split("-"); return parts.length===3?`${Number(parts[1])}.${Number(parts[2])}`:value; }
