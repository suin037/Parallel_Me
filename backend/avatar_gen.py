"""아바타 실사 이미지 생성.

빌더가 만든 SVG 아바타를 구운 PNG 를 '참조 이미지'로 받아, 같은 인물의
실사 초상을 생성한다. 참조 이미지가 얼굴·헤어·피부톤을 고정해 주므로
생성할 때마다 다른 사람이 나오는 문제를 억제한다.

주의: Claude API 는 이미지 '입력'만 지원하고 이미지 생성 기능이 없다.
그래서 ANTHROPIC_API_KEY 로는 이 기능을 쓸 수 없고, 이미지 생성 서비스의
키가 따로 필요하다. 프로바이더는 _call_provider 한 곳에만 묶어 두었다.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from pathlib import Path

from config import settings

# 생성 결과를 디스크에 캐싱한다. 같은 아바타는 두 번 생성하지 않는다.
CACHE_DIR = Path(__file__).resolve().parent / "artifacts" / "avatars"

_DATA_URL_RE = re.compile(r"^data:image/png;base64,(?P<b64>[A-Za-z0-9+/=\s]+)$")

# 참조 이미지 상한. 512px PNG 는 보통 수백 KB 라 넉넉한 값.
MAX_REFERENCE_BYTES = 4 * 1024 * 1024


class AvatarGenError(RuntimeError):
    """생성 실패. message 는 사용자에게 그대로 보여줘도 되는 한국어 문장."""


def decode_reference(data_url: str) -> bytes:
    """프론트가 보낸 PNG dataURL 을 바이트로. 형식이 어긋나면 AvatarGenError."""
    m = _DATA_URL_RE.match((data_url or "").strip())
    if not m:
        raise AvatarGenError("참조 이미지 형식이 올바르지 않습니다. PNG dataURL 이어야 합니다.")
    try:
        raw = base64.b64decode(m.group("b64"), validate=True)
    except (binascii.Error, ValueError):
        raise AvatarGenError("참조 이미지를 디코드하지 못했습니다.")
    if not raw:
        raise AvatarGenError("참조 이미지가 비어 있습니다.")
    if len(raw) > MAX_REFERENCE_BYTES:
        raise AvatarGenError("참조 이미지가 너무 큽니다(4MB 초과).")
    return raw


def _cache_path(reference: bytes, prompt: str) -> Path:
    """참조 이미지 + 프롬프트가 같으면 같은 파일을 가리키는 경로."""
    digest = hashlib.sha256(reference + prompt.encode("utf-8")).hexdigest()[:32]
    return CACHE_DIR / f"{digest}.png"


def _to_data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _call_provider(reference_png: bytes, prompt: str) -> bytes:
    """이미지 생성 서비스를 호출해 PNG 바이트를 돌려준다.

    프로바이더에 종속되는 유일한 지점이다. 어떤 서비스를 쓸지 정해지면
    여기만 채우면 나머지 파이프라인(캐시·검증·라우트·프론트)은 그대로 동작한다.

    참조 이미지를 입력으로 받는(image-to-image / image editing) 엔드포인트여야
    한다. 텍스트만 받는 엔드포인트는 아바타 일관성을 지키지 못한다.
    """
    provider = (settings.avatar_image_provider or "").strip().lower()
    if not provider:
        raise AvatarGenError(
            "이미지 생성 프로바이더가 설정되지 않았습니다. "
            ".env 에 AVATAR_IMAGE_PROVIDER 와 해당 키를 넣어주세요."
        )
    raise AvatarGenError(
        f"'{provider}' 프로바이더 연동이 아직 구현되지 않았습니다. "
        "backend/avatar_gen.py 의 _call_provider 를 채워주세요."
    )


def generate(reference_data_url: str, prompt: str) -> str:
    """참조 이미지 + 프롬프트 → 실사 아바타 PNG dataURL. 캐시 우선."""
    if not (prompt or "").strip():
        raise AvatarGenError("프롬프트가 비어 있습니다.")

    reference = decode_reference(reference_data_url)
    path = _cache_path(reference, prompt)
    if path.exists():
        return _to_data_url(path.read_bytes())

    png = _call_provider(reference, prompt)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return _to_data_url(png)
