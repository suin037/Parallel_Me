// 레벨 보상은 예측 결과와 무관한 꾸미기 전용 기능이다.
// `type`별 렌더러가 준비되는 순서대로 실제 선택 화면에 연결한다.
export const LEVEL_REWARDS = [
  {
    id: "constellation_aurora",
    level: 6,
    type: "constellationTheme",
    name: "오로라 별자리",
    description: "별자리 선과 별빛에 오로라 색을 더해요.",
    value: "aurora",
  },
  {
    id: "mascot_cosmic",
    level: 10,
    type: "mascotSkin",
    name: "코스믹 코스모",
    description: "코스모의 특별 탐험가 스킨이에요.",
    value: "cosmic",
  },
  {
    id: "universe_deep_nebula",
    level: 15,
    type: "universeTheme",
    name: "심해 성운",
    description: "나의 우주를 깊은 성운 테마로 꾸며요.",
    value: "deep-nebula",
  },
  {
    id: "profile_galaxy",
    level: 20,
    type: "profileFrame",
    name: "은하 프로필 프레임",
    description: "아바타 둘레에 특별한 은하 프레임을 표시해요.",
    value: "galaxy",
  },
];

export function unlockedRewards(level) {
  return LEVEL_REWARDS.filter((reward) => level >= reward.level);
}

export function nextReward(level) {
  return LEVEL_REWARDS.find((reward) => reward.level > level) || null;
}

export function isUnlocked(id, level) {
  const reward = LEVEL_REWARDS.find((item) => item.id === id);
  return !reward || level >= reward.level;
}
