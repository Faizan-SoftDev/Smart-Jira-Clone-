"""REST tests for session, reset, and JWT authentication flows."""

from django.contrib.auth.tokens import default_token_generator
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APITestCase

from .models import RefreshToken, User


PASSWORD = "ComplexPassw0rd!"


class SessionAuthenticationApiTests(APITestCase):
    def test_register_creates_session_and_logout_ends_it(self):
        registration = self.client.post(
            reverse("auth-register"),
            {"email": "new@example.com", "display_name": "New User", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(registration.status_code, 201)
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 200)

        self.assertEqual(self.client.post(reverse("auth-logout")).status_code, 204)
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 403)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_changes_password_and_revokes_refresh_tokens(self):
        user = User.objects.create_user(email="person@example.com", display_name="Person", password=PASSWORD)
        RefreshToken.objects.create(user=user, expires_at=user.date_joined)
        requested = self.client.post(reverse("auth-password-reset"), {"email": user.email}, format="json")
        self.assertEqual(requested.status_code, 202)

        confirmed = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": default_token_generator.make_token(user),
                "password": "AnotherComplexPassw0rd!",
            },
            format="json",
        )
        self.assertEqual(confirmed.status_code, 204)
        user.refresh_from_db()
        self.assertTrue(user.check_password("AnotherComplexPassw0rd!"))
        self.assertFalse(RefreshToken.objects.filter(user=user, revoked_at__isnull=True).exists())


class JwtAuthenticationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="person@example.com", display_name="Person", password=PASSWORD)

    def test_token_pair_authenticates_and_refresh_rotation_blocks_replay(self):
        obtained = self.client.post(
            reverse("auth-token-obtain"), {"email": self.user.email, "password": PASSWORD}, format="json"
        )
        self.assertEqual(obtained.status_code, 200)
        self.assertIn("access", obtained.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {obtained.data['access']}")
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 200)

        self.client.credentials()
        refreshed = self.client.post(
            reverse("auth-token-refresh"), {"refresh": obtained.data["refresh"]}, format="json"
        )
        self.assertEqual(refreshed.status_code, 200)
        replay = self.client.post(
            reverse("auth-token-refresh"), {"refresh": obtained.data["refresh"]}, format="json"
        )
        self.assertEqual(replay.status_code, 400)
