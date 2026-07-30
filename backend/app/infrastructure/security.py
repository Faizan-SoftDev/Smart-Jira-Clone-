"""Password hashing and JWT primitives for authenticated API boundaries."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status


JWT_ALGORITHM = "HS256"
JWT_SECRET = os.getenv("JWT_SECRET", "")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a random salt."""
    import base64
    import hashlib
    import secrets

    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password without exposing timing-sensitive comparisons."""
    import base64
    import hashlib
    import hmac

    try:
        scheme, salt_text, digest_text = encoded_hash.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, role: str) -> str:
    """Issue a signed, expiring bearer token."""
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET must be configured")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": subject, "role": role, "iat": now, "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, str]:
    """Validate a bearer token and expose only its identity claims."""
    if not JWT_SECRET:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is unavailable")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        subject, role = payload.get("sub"), payload.get("role")
        if not isinstance(subject, str) or not isinstance(role, str):
            raise ValueError("invalid claims")
        return {"sub": subject, "role": role}
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from exc
