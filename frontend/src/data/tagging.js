// ─────────────────────────────────────────────────────────────
// 일기 → 삶의 영역(행성) 분류를 한 곳으로 모은다.
//
// 여태 저장 경로마다 분류가 달랐다.
//   · 오늘 기록(DiaryToday)  키워드 + 서버 LLM  → 잘 붙음
//   · 마스코트 대화(ChatDiary) 키워드만          → 절반쯤 놓침
//   · 30초 체크인(DiaryCheckIn) 아무것도 안 함    → 어느 행성에도 안 붙음
//
// 안 붙은 기록은 나의 우주에 별로도 안 뜨고, 영역 점수·그래프에서도 빠진다.
// 즉 **적었는데 없는 셈이 된다.** 실제 데이터로 재보니 키워드만으로는 글 있는
// 기록의 46%가 아무 영역도 못 받았다. 놓친 것들이 이런 문장이다:
//   "몸이 자꾸 신호를 보낸다. 두통, 소화불량."      → 건강인데 못 잡음
//   "이력서 초안을 드디어 썼다."                    → 진로인데 못 잡음
//   "이게 맞나 싶다. 연봉은 나쁘지 않은데 삶이 없다." → 진로·삶의 만족인데 못 잡음
//
// 사람은 '건강'이라는 단어를 쓰지 않고 건강 이야기를 한다. 그래서 키워드는
// 즉시 붙이는 1차용으로만 쓰고, 서버 분류가 도착하면 합친다.
// 서버가 꺼져 있으면 키워드 결과만 남는다(없느니 낫다).
// ─────────────────────────────────────────────────────────────
import { LIFE_DOMAINS, detectLifeDomains } from "./choices.js";
import { tagDomain } from "./dispositionApi.js";
import { setDomains } from "./myUniverse.js";

const VALID = new Set(LIFE_DOMAINS.map((d) => d.key));

/**
 * 그 날짜 기록에 영역을 붙인다.
 *
 * 키워드로 잡히는 건 즉시 반환해 바로 쓰게 하고(저장 시 domains 로 넣으면 된다),
 * 서버 분류는 뒤따라와 합쳐 넣는다. 화면을 기다리게 하지 않는다.
 *
 * @returns {string[]} 즉시 붙일 수 있는 영역(키워드 결과)
 */
export function tagEntry(date, text) {
  const t = (text || "").trim();
  const immediate = t ? detectLifeDomains(t) : [];
  if (!t) return immediate;

  tagDomain(t).then((r) => {
    const fromServer = (r?.domains || []).filter((k) => VALID.has(k));
    const merged = [...new Set([...immediate, ...fromServer])];
    // 서버가 아무것도 못 주고 키워드도 비었으면 건드리지 않는다 —
    // 빈 배열을 써넣어 '분류 시도했음'처럼 보이게 만들 이유가 없다.
    if (merged.length) setDomains(date, merged);
  });

  return immediate;
}
