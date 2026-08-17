"""Cloudflare Workers AI를 이용한 RAG 서사 기반 아바타 장면 생성."""

import asyncio
import hashlib
import json
import logging
import time
import requests

from config import settings

log = logging.getLogger(__name__)


def _is_content_flag(response) -> bool:
    """Workers AI 안전 분류기에 걸린 응답인가.

    코드 3030("Your output has been flagged")으로 판별한다. 문구는 바뀔 수 있어
    코드를 먼저 보고, 본문이 JSON 이 아니면 문자열로 한 번 더 확인한다.
    """
    if response.status_code != 400:
        return False
    try:
        if any(e.get("code") == 3030 for e in (response.json().get("errors") or [])):
            return True
    except Exception:  # noqa: BLE001 - 본문이 JSON 이 아닌 경우
        pass
    return "flagged" in (response.text or "").lower()


VISUAL_PROMPT_VERSION = "cinematic-3d-responsive-v6-gender"


def configured() -> bool:
    return bool(settings.cloudflare_account_id and settings.cloudflare_api_token)


def build_visual_prompt(choice: str, narrative: str, visual_scene: dict | None = None,
                        avatar_spec: dict | None = None, future_years: int = 3,
                        visual_format: str = "portrait 4:5") -> str:
    scene = json.dumps(visual_scene or {}, ensure_ascii=False, indent=2)
    identity = json.dumps(avatar_spec or {}, ensure_ascii=False, indent=2)
    selected_gender = (avatar_spec or {}).get("gender", "unspecified")
    if selected_gender == "male":
        gender_instruction = (
            "The user explicitly selected male. Depict this same character as male in both A and B "
            "scenes while preserving every visible identity attribute from input image 0."
        )
    elif selected_gender == "female":
        gender_instruction = (
            "The user explicitly selected female. Depict this same character as female in both A and B "
            "scenes while preserving every visible identity attribute from input image 0."
        )
    else:
        gender_instruction = (
            "The user did not specify gender. Do not infer or assign one; preserve the gender-neutral "
            "presentation of the character in input image 0."
        )
    return f"""
Create a premium cinematic stylized 3D story scene, like a high-quality animated feature
film still. Use the exact same single
avatar character shown in input image 0. Input image 0 is the character identity
reference, not merely a loose inspiration. Preserve the character's recognizable
face shape, eyes, eyebrows, nose, mouth, skin tone, hairstyle, hair color, glasses,
and head accessories if present. The person in the output must be immediately
recognizable as the character in input image 0.
{gender_instruction}
Do not exaggerate gender stereotypes or replace the selected avatar with a generic person.
Do not add makeup, facial hair, or a different haircut unless those attributes are explicitly
present in the avatar specification. These identity constraints are mandatory and override
any conflicting implication in the story or scene direction.

Exact avatar attributes to preserve:
{identity}
Do NOT copy the reference image's pose, circular frame, background, camera angle,
composition, or art style. Do not recreate a centered avatar portrait. Keep one shared,
unchanged wardrobe design and color palette for this character across both A and B scenes.
The A and B outputs are parallel futures of the EXACT SAME PERSON, not siblings, variants,
or two redesigned avatars. Identity consistency is mandatory. Both outputs must use the
same stylized 3D character rendering, material quality, facial proportions, wardrobe design,
cinematic lighting language, lens treatment, and overall production style.

Future choice: {choice}
Exact future timepoint: {future_years} years from the present. Depict the character at that
specific point in time, not an unspecified distant future and not a different time horizon.
Story to visualize: {narrative[:700]}
Scene direction:
{scene}

Stage one specific, instantly understandable moment from the story. Follow the scene
direction for location, action, body pose, expression, wardrobe, camera, lighting,
foreground, background, and meaningful objects. Build a detailed, layered environment
when the story supports it. Let the character interact naturally with the environment;
vary shot distance and camera angle instead of defaulting to a front-facing desk pose.
Polished stylized 3D animation aesthetic, physically believable materials, soft global
illumination, nuanced cinematic lighting and color, expressive but natural character acting,
subtle depth of field, detailed environment, strong visual storytelling. Compose specifically
for a {visual_format} result card. Fill the full frame with meaningful scene content and keep the
character and essential action inside the central safe area so the card needs no letterboxing.
The result must unmistakably be a coherent 3D-rendered scene, never a flat drawing.

No 2D illustration, no hand-drawn look, no anime, no flat vector art, no photorealistic live-action
person, no additional people, no split screen, no collage. Do not mix 2D and 3D techniques.
ABSOLUTELY NO typography or readable marks anywhere: no text, letters, words, Korean
characters, numbers, captions, subtitles, labels, signs, posters, screens, charts, logos,
watermarks, signatures, UI, book covers, document writing, or clothing print. Keep every
screen, sign, paper, book, package, and background surface blank or purely pictorial.
""".strip()


def _generate_one(avatar_png, choice, narrative, visual_scene, avatar_spec, future_years,
                  width, height, visual_format, seed):
    model = settings.cloudflare_reference_model
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{settings.cloudflare_account_id}/ai/run/{model}"
    )
    prompt = build_visual_prompt(
        choice, narrative, visual_scene, avatar_spec, future_years, visual_format
    )
    response = None
    max_attempts = max(1, settings.cloudflare_image_max_attempts)
    # 안전 분류기(code 3030)는 확률적이다 — 같은 프롬프트가 통과했다 막혔다 한다.
    # 그래서 seed 를 바꿔 다시 그리면 대개 통과한다. 예전엔 5xx 만 재시도하고
    # 400 은 즉시 포기해서, 한 번 걸리면 그 장면은 무조건 실패했다.
    attempt_seed = seed
    for attempt in range(max_attempts):
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {settings.cloudflare_api_token}"},
            data={
                "prompt": prompt,
                "width": str(width),
                "height": str(height),
                "seed": str(attempt_seed),
            },
            files={"input_image_0": ("avatar.png", avatar_png, "image/png")},
            # 읽기 상한을 240→90 으로 줄인다. 한 번 붙잡혀 있으면 재시도할 시간이
            # 없어져 프론트 타임아웃(60초)이 먼저 끊는다. 정상 생성은 10초대다.
            timeout=(30, 90),
        )
        if response.ok or attempt == max_attempts - 1:
            break
        if response.status_code >= 500:
            # Workers AI의 일시적인 5xx/동시 처리 실패는 짧게 기다렸다 재시도한다.
            time.sleep(0.5 * (attempt + 1))
        elif _is_content_flag(response):
            # 같은 seed 로 다시 보내면 결정적으로 또 막힌다. 반드시 바꾼다.
            attempt_seed = (attempt_seed * 7919 + 104729) % 2_000_000_000
            log.info("이미지 안전 분류기에 걸려 seed 를 바꿔 재시도한다 (%s)", choice)
        else:
            break  # 그 외 4xx 는 요청 자체가 잘못된 것이라 재시도해도 같다
    if not response.ok:
        try:
            detail = response.json()
            errors = detail.get("errors") or detail
            message = json.dumps(errors, ensure_ascii=False)[:500]
        except Exception:
            message = response.text[:500] or response.reason
        raise RuntimeError(f"Cloudflare image API {response.status_code}: {message}")
    payload = response.json()
    if not payload.get("success"):
        errors = "; ".join(e.get("message", "") for e in payload.get("errors", []))
        raise RuntimeError(errors or "Cloudflare image generation failed")
    image = (payload.get("result") or {}).get("image")
    if not image:
        raise RuntimeError("Cloudflare response did not contain an image")
    return f"data:image/jpeg;base64,{image}"


_PAIR_CACHE: dict[str, dict] = {}


async def generate_pair(
    avatar_png, choice_a, choice_b, narrative_a, narrative_b,
    visual_a=None, visual_b=None, avatar_spec=None, future_years=3,
    width=320, height=400, visual_format="portrait 4:5",
):
    if not configured():
        raise RuntimeError("Cloudflare Workers AI is not configured")
    if not avatar_png:
        raise ValueError("Avatar image is empty")
    cache_key = hashlib.sha256(
        avatar_png + json.dumps(
            [VISUAL_PROMPT_VERSION, future_years, width, height, visual_format,
             choice_a, choice_b, narrative_a, narrative_b, visual_a, visual_b, avatar_spec],
            ensure_ascii=False, sort_keys=True, default=str,
        ).encode("utf-8")
    ).hexdigest()
    if cache_key in _PAIR_CACHE:
        return _PAIR_CACHE[cache_key]
    # The two scenes are independent. Generate them concurrently so their
    # latencies do not add up.
    # 같은 참조 이미지와 seed를 사용해 A/B의 인물 정체성과 기본 화풍을 최대한 맞춘다.
    # 장면 차이는 choice·narrative·scene prompt가 만든다.
    identity_seed = 427
    # return_exceptions 가 없으면 한쪽이 실패한 순간 gather 가 그 예외를 올리고
    # **성공한 다른 한 장까지 버려진다**. 안전 분류기는 장면별로 걸리므로
    # 실제로 한 장만 막히는 경우가 흔한데, 화면은 A/B 이미지를 각각 쓰므로
    # (visuals?.a / visuals?.b) 한 장만 있어도 나머지는 아바타로 채워진다.
    results = await asyncio.gather(
        asyncio.to_thread(
            _generate_one, avatar_png, choice_a, narrative_a, visual_a, avatar_spec,
            future_years, width, height, visual_format, identity_seed
        ),
        asyncio.to_thread(
            _generate_one, avatar_png, choice_b, narrative_b, visual_b, avatar_spec,
            future_years, width, height, visual_format, identity_seed
        ),
        return_exceptions=True,
    )
    images = []
    for side, result in zip(("A", "B"), results):
        if isinstance(result, BaseException):
            log.warning("장면 이미지 %s 실패(아바타로 대체): %s: %s",
                        side, type(result).__name__, result)
            images.append(None)
        else:
            images.append(result)
    if all(image is None for image in images):
        # 둘 다 실패했으면 알린다 — 화면이 '이미지 없음'을 조용히 정상처럼
        # 보여주면 무엇이 고장났는지 아무도 모른다.
        raise RuntimeError("두 장면 이미지 생성이 모두 실패했습니다")
    pair = {"a": images[0], "b": images[1]}
    # 발표 중 같은 선택을 다시 실행하면 외부 모델을 재호출하지 않아 즉시 표시한다.
    # 단 **둘 다 성공했을 때만** 캐시한다 — 반쪽을 캐시하면 일시적인 분류기
    # 실패가 그 조합에서 영구히 굳어, 다시 눌러도 계속 한 장만 나온다.
    if all(images):
        if len(_PAIR_CACHE) >= 24:
            _PAIR_CACHE.pop(next(iter(_PAIR_CACHE)))
        _PAIR_CACHE[cache_key] = pair
    return pair
