# ─────────────────────────────────────────────────────────────
# 백엔드 at-rest 암호화 — SQLite에 저장되는 민감 컬럼(일기 원문·persona·리포트)을
# 저장 전 암호화, 조회 시 복호화한다. DB 파일이 탈취돼도 키 없이는 못 읽는다.
#
# 암호: Fernet (AES-128-CBC + HMAC 인증). 키는 서버 보유(env PM_SECRET_KEY 권장).
#   · 프로덕션: 환경변수 PM_SECRET_KEY(또는 KMS)에서 키를 받는다.
#   · 개발/데모: DB와 '분리된' 키파일(.pm_at_rest.key)을 생성해 쓴다(리포지토리 미포함).
#
# 정직선: 이건 Model B(서버 보관 키) — 서버는 복호 가능. "우리도 못 본다"까진 아니고
#   "DB 탈취·백업 유출에 강하다". (E2E는 프론트 클라 암호화 쪽에서 담당)
# 마이그레이션: 'enc:1:' 접두어로 암호문을 식별 → 기존 평문 행도 그대로 읽힌다(하위호환).
# ─────────────────────────────────────────────────────────────
import base64
import hashlib
import json
import os

from cryptography.fernet import Fernet

_PREFIX = "enc:1:"
_FERNET = None


def _resolve_key() -> bytes:
    env = os.getenv("PM_SECRET_KEY")
    if env:
        # 임의 문자열 → 유효한 Fernet 키(32B urlsafe base64)로 파생
        return base64.urlsafe_b64encode(hashlib.sha256(env.encode("utf-8")).digest())
    # 개발/데모: DB와 분리된 키파일. 프로덕션에선 env/KMS 사용 권장.
    keypath = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pm_at_rest.key")
    if os.path.exists(keypath):
        with open(keypath, "rb") as f:
            return f.read().strip()
    key = Fernet.generate_key()
    with open(keypath, "wb") as f:
        f.write(key)
    return key


def _fernet() -> Fernet:
    global _FERNET
    if _FERNET is None:
        _FERNET = Fernet(_resolve_key())
    return _FERNET


def enc_field(s):
    """문자열 → 'enc:1:'+암호문. None은 그대로."""
    if s is None:
        return None
    try:
        return _PREFIX + _fernet().encrypt(str(s).encode("utf-8")).decode("ascii")
    except Exception as exc:
        # 민감정보는 암호화 실패 시 평문으로 저장하지 않는다(fail closed).
        raise RuntimeError("민감정보 암호화에 실패해 저장을 중단했습니다.") from exc


def dec_field(s):
    """'enc:1:'+암호문 → 원문. 접두어 없으면 평문으로 간주(하위호환)."""
    if s is None:
        return None
    if not isinstance(s, str) or not s.startswith(_PREFIX):
        return s
    try:
        return _fernet().decrypt(s[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except Exception:
        return None  # 복호 실패(키 불일치/변조)


def enc_json(obj):
    if obj is None:
        return None
    return enc_field(json.dumps(obj, ensure_ascii=False))


def dec_json(s):
    raw = dec_field(s)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def is_encrypted(s) -> bool:
    return isinstance(s, str) and s.startswith(_PREFIX)
