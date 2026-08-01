"""JWT creation and refresh rotation with server-side revocation records."""

from __future__ import annotations

from datetime import timedelta

import jwt
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import RefreshToken, User


def _encode(*, user: User, token_type: str, expires_at, token_id: str | None = None) -> str:
    payload = {
        "sub": str(user.pk),
        "type": token_type,
        "iat": timezone.now(),
        "exp": expires_at,
        "iss": settings.JWT_ISSUER,
    }
    if token_id:
        payload["jti"] = token_id
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm="HS256")


def issue_token_pair(*, user: User) -> dict[str, str]:
    """Create a 15-minute access token and persisted seven-day refresh token."""
    now = timezone.now()
    refresh = RefreshToken.objects.create(
        user=user,
        expires_at=now + timedelta(seconds=settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS),
    )
    return {
        "access": _encode(
            user=user,
            token_type="access",
            expires_at=now + timedelta(seconds=settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS),
        ),
        "refresh": _encode(user=user, token_type="refresh", expires_at=refresh.expires_at, token_id=str(refresh.pk)),
    }


def decode_refresh_token(token: str) -> RefreshToken:
    """Decode a refresh JWT and verify that its persisted identity is still usable."""
    try:
        payload = jwt.decode(token, settings.JWT_SIGNING_KEY, algorithms=["HS256"], issuer=settings.JWT_ISSUER)
    except jwt.PyJWTError as exc:
        raise ValueError("Invalid or expired refresh token.") from exc
    if payload.get("type") != "refresh" or not payload.get("jti"):
        raise ValueError("Refresh token required.")
    try:
        refresh = RefreshToken.objects.select_related("user").get(pk=payload["jti"])
    except RefreshToken.DoesNotExist as exc:
        raise ValueError("Refresh token has been revoked.") from exc
    if refresh.revoked_at or refresh.expires_at <= timezone.now() or not refresh.user.is_active:
        raise ValueError("Refresh token has been revoked or expired.")
    return refresh


def rotate_refresh_token(*, token: str) -> dict[str, str]:
    """Revoke a used refresh token and issue a new pair, preventing replay."""
    with transaction.atomic():
        decoded = decode_refresh_token(token)
        try:
            refresh = RefreshToken.objects.select_for_update().select_related("user").get(pk=decoded.pk)
        except RefreshToken.DoesNotExist as exc:  # defensive protection against a concurrent revoke
            raise ValueError("Refresh token has been revoked.") from exc
        if refresh.revoked_at:
            raise ValueError("Refresh token has been revoked or expired.")
        refresh.revoked_at = timezone.now()
        refresh.save(update_fields=["revoked_at"])
        return issue_token_pair(user=refresh.user)
