"""셀카 한 장 → 아바타 설정.

카메라 프레임을 Claude 에게 보여주고 '우리 빌더에 있는 선택지 중 무엇인지'를 고르게 한다.
브라우저 랜드마크(MediaPipe)로는 헤어스타일·안경·수염을 알 수 없는데, 보는 모델은 고를 수 있다.

사진 취급 원칙
  - 디스크에 쓰지 않는다. 메모리에서만 다루고 응답 후 버린다.
  - 로그에 이미지(또는 그 일부)를 남기지 않는다.
  - 저장되는 것은 반환하는 설정 JSON 뿐이다.
  다만 '전송은 일어난다' — Anthropic 으로 이미지가 올라간다. 기기를 안 떠나는
  온디바이스 방식과는 다르므로 화면 문구를 그에 맞게 써야 한다.

선택지 목록은 프론트가 함께 보낸다. 백엔드에 목록을 복사해두면 avatarOptions.js 와
갈라지기 때문이다 — 프론트에 헤어스타일을 추가하면 여기서도 자동으로 후보가 된다.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re

from anthropic import Anthropic

from config import settings

log = logging.getLogger(__name__)

_client: Anthropic | None = None

# data URL 상한. 640px 정도 프레임이면 보통 100~300KB 다.
MAX_IMAGE_BYTES = 5 * 1024 * 1024
_DATA_URL_RE = re.compile(r"^data:image/(?P<kind>png|jpeg|jpg|webp);base64,(?P<b64>[A-Za-z0-9+/=\s]+)$")

# 색은 목록에서 고르게 할 이유가 없다 — DiceBear 는 임의 hex 를 받는다.
# 프리셋으로 가두면 실제 머리색·피부색과 어긋나는 게 눈에 띈다. 그래서 이 항목만
# enum 대신 자유 문자열로 받고, 아래 _clean_hex 로 검증한다.
# (스키마에 pattern 을 걸 수도 있지만 지원 범위가 불확실해 파이썬 쪽에서 검증한다.)
HEX_FIELDS = {"skinColor", "hairColor", "clothesColor"}
_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _clean_hex(value: str) -> str | None:
    """'#3B2A1F' / '3b2a1f' → '3b2a1f'. 형식이 아니면 None."""
    m = _HEX_RE.match((value or "").strip())
    return m.group(1).lower() if m else None


# 프론트가 보낼 수 있는 항목. 여기 없는 키는 무시한다(임의 스키마 주입 방지).
ALLOWED_FIELDS = {
    "face", "hairStyle", "eyes", "eyebrows", "browThickness",
    "mouth", "glasses", "beard", "skinColor", "hairColor",
    "clothes", "clothesColor",
}

PROMPT = """이 사진 속 인물을 보고, 아래 목록에서 가장 닮은 항목을 하나씩 고르세요.

먼저 faceVisible 을 판단하세요. 얼굴이 화면에 충분히 크고 또렷하게 보이면 true,
얼굴이 없거나·너무 작거나·심하게 어둡거나·크게 잘렸으면 false 입니다.
false 여도 나머지 항목은 무난한 값으로 채우세요(적용되지 않습니다).

각 항목은 반드시 주어진 값 중 하나여야 합니다.

**모든 항목을 무난한 값으로 채우지 마세요.** 특히 얼굴형·눈·눈썹은 사람마다 다릅니다.
확신이 100%가 아니어도 사진에서 실제로 보이는 쪽을 고르세요. 애매하다고 매번 같은
값을 고르면 아무도 자기 얼굴로 느끼지 못합니다.

■ 얼굴형 — 턱선만 보고 판단하세요
    턱 끝이 좁게 모이는가, 턱선이 각지는가, 얼굴이 세로로 긴가 짧은가.
    광대나 헤어스타일이 아니라 턱 모양이 기준입니다.

■ 눈 크기(eyeScale) — 숫자로 적으세요. 무엇과 비교하는지가 중요합니다.

    **사진 속 인물과 같은 인종·성별인 사람들 사이에서** 비교하세요.
    서양인 평균이나 만화 캐릭터와 비교하면 안 됩니다. 그렇게 하면 동아시아 얼굴이
    전부 '작음'으로 몰리는데, 그건 판단을 안 한 것과 같습니다.

    같은 인종의 사람 열 명을 세워놓았다고 치고, 그 안에서 어디쯤인지를 적으세요.
      0.72~0.88  그 열 명 중에서도 눈이 작은 편
      0.90~1.00  그 열 명의 한가운데
      1.02~1.10  그 열 명 중에서도 눈이 큰 편
    애매하면 1.00 으로 도망가지 말고 실제로 보이는 쪽으로 기울이세요.

■ 눈썹 굵기(browWeight) — 픽셀 굵기를 숫자로. 8~24 사이.
    이것도 같은 인종·성별 사람들 사이에서 비교합니다.
      8~11   그 중에서도 가늘게 정리된 눈썹
      13~16  그 중 보통
      19~24  그 중에서도 굵고 짙은 눈썹

■ 눈 모양 — 눈꺼풀이 덮는 정도와 가로세로 비율
    위아래로 크게 떠서 흰자가 많이 보이는지, 아래 눈꺼풀이 올라와 웃는 모양인지,
    가늘고 옆으로 긴지. (동아시아 인물 사진에서는 가는 눈이 흔하지만,
    그렇다고 전부 같은 값으로 몰지는 마세요.)

■ 눈썹 — 모양은 눈썹 산의 각도, 두께는 실제 굵기를 보고 따로 고르세요.
■ 표정 — 입 모양만 보고 고르세요. 눈은 표정 판단에 쓰지 마세요.

■ 헤어스타일 — 이 순서로 좁히세요
    0) **머리를 묶었는가**. 묶었으면 길이·앞머리와 상관없이 번머리(bun)입니다.
         정수리나 뒤통수에서 머리가 하나로 모임 / 뒷목이 드러남 / 옆에 잔머리만
         남아 있음 — 이 중 하나라도 보이면 묶은 것입니다.
         포니테일·반묶음 파츠가 따로 없어서 번머리가 그 자리를 대신합니다.
    1) 이마가 드러나는가
         이마 한가운데가 보이면        → 가르마 계열
         이마가 대부분 머리에 덮였으면 → 덮머 계열
         한쪽으로 쓸어넘겨 이마가 절반쯤 보여도 → 가르마입니다
    2) 길이 (귀 위 / 귀 아래 / 어깨 아래)
    3) 곱슬인가 직모인가
         곱슬이 뚜렷하지 않은데 가르마라면 펌 항목이 아니라 옆가르마를 고르세요.
    성별로 고르지 마세요. 머리가 긴 남성은 긴머리 항목을 고르는 것이 맞습니다.

- 안경이 없으면 none, 수염이 없으면 null 을 고르세요.
- lashes 는 속눈썹이 눈에 띄게 길거나 짙게 보일 때만 true 입니다. 잘 안 보이면 false 로 두세요.
- 피부색·머리색·의상 컬러는 목록에서 고르지 말고, 사진에서 본 실제 색을
  6자리 hex 로 적으세요(예: "3b2a1f").
  머리색은 그늘진 뿌리가 아니라 빛을 받는 중간 톤을 기준으로 적으세요.
  갈색기가 조금이라도 보이면 검정(#1a1a1a 류)이 아니라 갈색으로 적어야 합니다.
- 의상은 옷깃·목선 모양을 보고 고르세요. 잘 안 보이면 티셔츠를 고르세요.
- 옷 무늬(pattern)는 실제로 보이는 대로 숫자로 적으세요.
    kind  : 무늬 없으면 none, 줄무늬 stripe, 물방울 dot, 격자 check
    color : 무늬 색 6자리 hex. 넓은 면적을 차지하는 쪽이 바탕(clothesColor)이고,
            그 위에 얹힌 좁은 쪽이 무늬입니다. 둘을 바꿔 넣지 마세요.
    size  : 무늬 한 칸 크기. 얼굴 폭이 약 380 인 좌표계 기준이라
            가는 줄무늬는 20 안팎, 굵은 줄무늬는 50 안팎입니다.
    angle : 0=가로줄, 90=세로줄, 45=사선
  옷이 안 보이거나 무늬가 없으면 kind 를 none 으로 하고 나머지는 아무 값이나 넣으세요.

인물을 평가하거나 설명하지 말고, 선택 결과만 내보내세요."""


class AvatarVisionError(RuntimeError):
    """사용자에게 그대로 보여줘도 되는 한국어 실패 사유."""


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise AvatarVisionError("ANTHROPIC_API_KEY 가 설정되지 않았습니다.")
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _decode(data_url: str) -> tuple[str, bytes]:
    m = _DATA_URL_RE.match((data_url or "").strip())
    if not m:
        raise AvatarVisionError("이미지 형식이 올바르지 않습니다.")
    try:
        raw = base64.b64decode(m.group("b64"), validate=True)
    except (binascii.Error, ValueError):
        raise AvatarVisionError("이미지를 디코드하지 못했습니다.")
    if not raw:
        raise AvatarVisionError("이미지가 비어 있습니다.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise AvatarVisionError("이미지가 너무 큽니다(5MB 초과).")
    kind = m.group("kind")
    return ("image/jpeg" if kind == "jpg" else f"image/{kind}"), raw


def _legend(options: dict) -> str:
    """선택지 id 가 무슨 뜻인지 프롬프트에 붙인다.

    id 만 주면 모델이 'pointedShort' 가 어떤 턱 모양인지 알 방법이 없다. 실제로
    얼굴형이 열 장 내내 oval 하나로만 나왔다 — 고른 게 아니라 무난한 값에 몰린 것이다.
    라벨은 프론트가 함께 보낸다(avatarOptions.js 가 원본이라 여기 복사해두면 갈라진다).
    """
    labels = (options or {}).get("labels") or {}
    lines = []
    for field, mapping in labels.items():
        if field not in ALLOWED_FIELDS or not isinstance(mapping, dict):
            continue
        allowed = options.get(field) or []
        pairs = [f"{k}={v}" for k, v in mapping.items() if k in allowed]
        if pairs:
            lines.append(f"  {field}: " + ", ".join(pairs))
    if not lines:
        return ""
    return "\n\n선택지 id 의 뜻:\n" + "\n".join(lines)


def _build_schema(options: dict) -> dict:
    """프론트가 보낸 선택지로 JSON 스키마를 만든다.

    enum 으로 묶어두면 우리 목록에 없는 값이 아예 나올 수 없어서, 응답을 그대로
    config 에 꽂아도 안전하다.
    """
    props: dict = {}
    for field, values in (options or {}).items():
        if field not in ALLOWED_FIELDS:
            continue
        if field in HEX_FIELDS:
            # 목록은 참고용으로만 쓰고(프롬프트에 예시로 들어감) 값은 자유롭게 받는다.
            props[field] = {"type": "string"}
            continue
        vals = [v for v in values if isinstance(v, str)]
        if not vals:
            continue
        # 수염처럼 '없음'이 있는 항목은 null 도 허용한다.
        # type 을 배열로 쓰면(["string","null"]) API 가 거부한다 —
        #   "Enum value 'chin' does not match declared type '['string','null']'"
        # anyOf 로 감싸야 통과한다.
        nullable = any(v is None for v in values)
        props[field] = (
            {"anyOf": [{"type": "string", "enum": vals}, {"type": "null"}]}
            if nullable
            else {"type": "string", "enum": vals}
        )
    if not props:
        raise AvatarVisionError("선택지 목록이 비어 있습니다.")
    # 얼굴이 제대로 안 잡혔는지 모델이 직접 알려주게 한다.
    # 라이브 얼굴 검출을 붙이려면 별도 모델(MediaPipe 등)이 필요해서, 촬영 후 판정으로 대신한다.
    props["faceVisible"] = {"type": "boolean"}
    # 빌트인 눈에는 속눈썹이 항상 붙어 있어서, 그대로 두면 남자 사진에서도 여성적으로 보인다.
    # '남자인지'를 묻는 대신 '속눈썹이 실제로 보이는지'를 묻는다 — 성별을 추정하지 않아도
    # 원하는 결과가 나오고, 사진에 있는 것만 보고 판단하므로 더 정확하다.
    props["lashes"] = {"type": "boolean"}
    # 눈 크기·눈썹 굵기는 목록에서 고르게 하면 매번 같은 칸에 몰린다.
    # (실사진 10장 눈 10/10 'small', 우리 그림에 정답을 넣고 물어도 눈 1/3)
    # 원인은 비교 기준이었다 — 만화 그림에는 전부 '크다', 사람 사진에는 전부 '작다'.
    # 숫자로 받고 프롬프트에서 '사람 사진들의 평균이 1.0' 이라고 못 박는다.
    props["eyeScale"] = {"type": "number"}
    props["browWeight"] = {"type": "number"}
    # 옷 무늬는 목록에서 고르는 게 아니라 숫자로 받아 즉석에서 그린다.
    # 프리셋을 두면 실제 줄무늬 굵기·각도·색을 못 맞춘다.
    props["pattern"] = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["none", "stripe", "dot", "check"]},
            "color": {"type": "string"},
            "size": {"type": "number"},
            "angle": {"type": "number"},
        },
        "required": ["kind", "color", "size", "angle"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


def analyze(image_data_url: str, options: dict) -> dict:
    """사진 + 선택지 → {"config": 설정, "face_visible": 얼굴이 제대로 잡혔는지}."""
    media_type, raw = _decode(image_data_url)
    schema = _build_schema(options)
    prompt = PROMPT + _legend(options)

    try:
        response = _get_client().messages.create(
            model=settings.avatar_vision_model,
            max_tokens=1024,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.b64encode(raw).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
    except AvatarVisionError:
        # 키 미설정처럼 사용자가 바로 조치할 수 있는 원인은 일반 오류로 덮지 않는다.
        raise
    except Exception as e:  # 네트워크·인증·정책 등
        log.warning("아바타 비전 호출 실패: %s", type(e).__name__)  # 이미지는 로그에 남기지 않는다
        raise AvatarVisionError("사진 분석에 실패했습니다. 잠시 후 다시 시도해주세요.")

    if response.stop_reason == "refusal":
        raise AvatarVisionError("이 사진은 분석할 수 없습니다. 다른 사진으로 시도해주세요.")

    text = next((b.text for b in response.content if b.type == "text"), "")
    if not text:
        raise AvatarVisionError("사진에서 아바타 설정을 얻지 못했습니다.")

    import json

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise AvatarVisionError("사진 분석 결과를 해석하지 못했습니다.")

    face_visible = bool(data.pop("faceVisible", True))

    # 색은 자유 입력이라 여기서 검증한다. 형식이 아니면 그 항목만 버린다
    # (프론트가 기존 값을 유지하므로 아바타가 깨지지 않는다).
    # 무늬는 자유 입력이라 범위를 여기서 잡는다(스키마에 최소/최대를 못 걸어서).
    pat = data.get("pattern")
    if isinstance(pat, dict):
        kind = pat.get("kind")
        if kind not in ("stripe", "dot", "check"):
            data["pattern"] = {"kind": "none"}
        else:
            color = _clean_hex(str(pat.get("color", "")))
            try:
                size = float(pat.get("size", 40))
            except (TypeError, ValueError):
                size = 40.0
            try:
                angle = float(pat.get("angle", 0))
            except (TypeError, ValueError):
                angle = 0.0
            data["pattern"] = {
                "kind": kind,
                "color": color or "ffffff",
                "size": max(8.0, min(120.0, size)),
                "angle": max(0.0, min(180.0, angle)),
            }
    else:
        data.pop("pattern", None)

    # 숫자 두 개는 자유 입력이라 범위를 여기서 잡는다.
    for field, lo, hi, default in (("eyeScale", 0.7, 1.12, 1.0), ("browWeight", 8.0, 24.0, 14.0)):
        try:
            data[field] = max(lo, min(hi, float(data.get(field, default))))
        except (TypeError, ValueError):
            data[field] = default

    for field in HEX_FIELDS & data.keys():
        cleaned = _clean_hex(data[field])
        if cleaned:
            data[field] = cleaned
        else:
            del data[field]

    return {"config": data, "face_visible": face_visible}
