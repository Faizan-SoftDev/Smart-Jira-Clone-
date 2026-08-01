"""RFC 6238-compatible TOTP generation and verification without client secrets."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from django.contrib.auth.hashers import make_password


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def generate_recovery_codes(count: int = 8) -> list[str]:
    return [secrets.token_urlsafe(6).upper() for _ in range(count)]


def verify_code(secret: str, code: str, window: int = 1) -> bool:
    """Accept a six-digit code within one adjacent 30-second window."""
    if not code.isdigit() or len(code) != 6:
        return False
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    counter = int(time.time() // 30)
    for offset in range(-window, window + 1):
        digest = hmac.new(key, struct.pack(">Q", counter + offset), hashlib.sha1).digest()
        index = digest[-1] & 15
        token = (struct.unpack(">I", digest[index:index + 4])[0] & 0x7fffffff) % 1_000_000
        if hmac.compare_digest(f"{token:06d}", code):
            return True
    return False
