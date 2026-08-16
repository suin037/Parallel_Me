// 앞말의 받침 유무에 따라 조사를 고른다. "진로을 높이면" 같은 표기를 없앤다.
//
// 한글 음절은 0xAC00 + (초성*21 + 중성)*28 + 종성 으로 배열되어 있다.
// 따라서 (코드 - 0xAC00) % 28 이 0 이면 종성(받침)이 없다.

/** 마지막 글자에 받침이 있으면 true. 한글 음절이 아니면 false. */
export function hasFinalConsonant(word) {
  const last = (word || "").trim().slice(-1);
  if (!last) return false;
  const code = last.charCodeAt(0);
  if (code < 0xac00 || code > 0xd7a3) return false;
  return (code - 0xac00) % 28 !== 0;
}

/**
 * 받침 유무에 맞는 조사를 붙여 돌려준다.
 *   josa("진로", "을", "를") → "진로를"
 *   josa("건강", "을", "를") → "건강을"
 */
export function josa(word, withFinal, withoutFinal) {
  return `${word}${hasFinalConsonant(word) ? withFinal : withoutFinal}`;
}
