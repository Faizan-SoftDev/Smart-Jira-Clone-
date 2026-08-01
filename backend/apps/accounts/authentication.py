"""Bearer-token authentication backed by TaskCraft's revocable refresh sessions."""

from __future__ import annotations

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class JWTAuthentication(BaseAuthentication):
    """Authenticate a short-lived signed access token from an Authorization header."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            raise AuthenticationFailed("Use an Authorization header with a Bearer token.")
        try:
            payload = jwt.decode(
                parts[1],
                settings.JWT_SIGNING_KEY,
                algorithms=["HS256"],
                issuer=settings.JWT_ISSUER,
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationFailed("Invalid or expired access token.") from exc
        if payload.get("type") != "access":
            raise AuthenticationFailed("Access token required.")
        try:
            user = get_user_model().objects.get(pk=payload["sub"], is_active=True)
        except (KeyError, get_user_model().DoesNotExist) as exc:
            raise AuthenticationFailed("User account is unavailable.") from exc
        return user, payload
