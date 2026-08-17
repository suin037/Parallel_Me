import { API_BASE } from "./apiBase.js";
import { maskText } from "./outbound.js";
// 관계 분석 — 대화·연락 내역(텍스트·화면 캡처) × 내 성향. 특정 메신저에 매이지 않는다.
// 서버(qmode api)가 관계 신호를 뽑고 성향과 엮어 '선택지형' 서사를 만든다.
// 위기 신호가 감지되면 분석 대신 지원 안내를 돌려준다(blocked).
const BASE = API_BASE;

export async function analyzeRelationship(talk, uid = "me") {
  const res = await fetch(`${BASE}/relationship/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      uid,
      relation_tag: talk.tag || null,     // 같은 상대로 쌓이면 변화 추적이 켜진다
      label: talk.label || null,
      // 화면(RelationshipInput)에서도 한 번 가리지만 여기서 다시 건다 — 다른 경로로
      // 이 함수를 부르면 그 마스킹을 통째로 우회하기 때문. 마스킹은 여러 번 걸어도 같다.
      transcript: talk.transcript ? maskText(talk.transcript) : null,
      images: (talk.images || []).map((im) => ({ media_type: im.media_type, data: im.data })),
    }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

/** 같은 상대의 스냅샷 시계열 — 2개 이상 쌓이면 변화가 보인다. */
export async function relationshipTimeline(tag, uid = "me") {
  const res = await fetch(`${BASE}/relationship/${encodeURIComponent(uid)}/${encodeURIComponent(tag)}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}
