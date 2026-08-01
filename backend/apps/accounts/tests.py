"""Tests for email-based platform identity."""

from django.test import TestCase

from .models import User


class UserModelTests(TestCase):
    def test_email_is_normalized_and_used_as_identity(self):
        user = User.objects.create_user(
            email="Faizan@EXAMPLE.COM", password="safe-test-password", display_name="Faizan"
        )

        self.assertEqual(user.email, "faizan@example.com")
        self.assertTrue(user.check_password("safe-test-password"))
        self.assertEqual(User.USERNAME_FIELD, "email")
