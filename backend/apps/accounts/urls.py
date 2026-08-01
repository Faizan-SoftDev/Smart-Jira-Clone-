"""Authentication API routing."""

from django.urls import path

from .api import (
    CsrfTokenView, CurrentUserView, LoginView, LogoutView, PasswordResetConfirmView,
    PasswordResetRequestView, RegisterView, TokenObtainView, TokenRefreshView, TokenRevokeView, TOTPEnrollmentView, TOTPConfirmView, RecoveryCodeGenerationView, RecoveryCodeVerifyView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", CurrentUserView.as_view(), name="auth-me"),
    path("auth/csrf/", CsrfTokenView.as_view(), name="auth-csrf"),
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("auth/token/", TokenObtainView.as_view(), name="auth-token-obtain"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/token/revoke/", TokenRevokeView.as_view(), name="auth-token-revoke"),
    path("auth/totp/enroll/", TOTPEnrollmentView.as_view(), name="auth-totp-enroll"),
    path("auth/totp/confirm/", TOTPConfirmView.as_view(), name="auth-totp-confirm"),
    path("auth/recovery-codes/", RecoveryCodeGenerationView.as_view(), name="auth-recovery-codes"),
    path("auth/recovery-codes/verify/", RecoveryCodeVerifyView.as_view(), name="auth-recovery-code-verify"),
]
