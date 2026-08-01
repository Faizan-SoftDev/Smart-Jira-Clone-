"""Session and JWT authentication endpoints without exposing account existence."""

from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils import timezone
from django.middleware.csrf import get_token
from django.contrib.auth.hashers import check_password, make_password
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RefreshToken, User
from .models import TOTPDevice
from .models import RecoveryCode
from .totp import generate_recovery_codes, generate_secret, verify_code
from .policies import has_confirmed_two_factor, requires_two_factor
from .tokens import decode_refresh_token, issue_token_pair, rotate_refresh_token


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "display_name", "date_joined")
        read_only_fields = fields


class RegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    display_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        validate_password(attrs["password"], user=User(email=attrs["email"], display_name=attrs["display_name"]))
        return attrs


class CredentialsSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    totp_code = serializers.CharField(required=False, allow_blank=False, min_length=6, max_length=6, write_only=True)


def authenticate_credentials(request, credentials):
    """Authenticate credentials and enforce Enterprise TOTP policy before issuing a session."""
    user = authenticate(request, email=credentials["email"], password=credentials["password"])
    if user is None:
        raise AuthenticationFailed("Invalid email or password.")
    if requires_two_factor(user):
        if not has_confirmed_two_factor(user):
            raise AuthenticationFailed("Two-factor enrollment is required for this workspace.")
        if not verify_code(user.totp_device.secret, credentials.get("totp_code", "")):
            raise AuthenticationFailed("A valid two-factor authentication code is required.")
    return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class TOTPConfirmSerializer(serializers.Serializer):
    code = serializers.CharField(min_length=6, max_length=6)


class RecoveryCodeSerializer(serializers.Serializer):
    code = serializers.CharField()


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True), name="post")
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.create_user(**serializer.validated_data)
        login(request, user)
        return Response({"user": UserSerializer(user).data}, status=201)


@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="post")
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CredentialsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_credentials(request, serializer.validated_data)
        login(request, user)
        return Response({"user": UserSerializer(user).data})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=204)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class CsrfTokenView(APIView):
    """Set the CSRF cookie and return the matching token for the SPA client."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True), name="post")
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        form = PasswordResetForm({"email": serializer.validated_data["email"]})
        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name="accounts/password_reset_email.html",
                subject_template_name="accounts/password_reset_subject.txt",
            )
        # Always return the same response to prevent account enumeration.
        return Response(status=202)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = get_user_model().objects.get(pk=force_str(urlsafe_base64_decode(serializer.validated_data["uid"])))
        except (ValueError, TypeError, OverflowError, get_user_model().DoesNotExist):
            raise serializers.ValidationError({"token": "Invalid password reset link."})
        if not default_token_generator.check_token(user, serializer.validated_data["token"]):
            raise serializers.ValidationError({"token": "Invalid or expired password reset link."})
        validate_password(serializer.validated_data["password"], user=user)
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        RefreshToken.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=timezone.now())
        return Response(status=204)


@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="post")
class TokenObtainView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CredentialsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_credentials(request, serializer.validated_data)
        return Response(issue_token_pair(user=user))


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(rotate_refresh_token(token=serializer.validated_data["refresh"]))
        except ValueError as exc:
            raise serializers.ValidationError({"refresh": str(exc)}) from exc


class TokenRevokeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh = decode_refresh_token(serializer.validated_data["refresh"])
        except ValueError as exc:
            raise serializers.ValidationError({"refresh": str(exc)}) from exc
        refresh.revoked_at = refresh.created_at
        refresh.save(update_fields=["revoked_at"])
        return Response(status=204)


class TOTPEnrollmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        device, _ = TOTPDevice.objects.get_or_create(user=request.user, defaults={"secret": generate_secret()})
        if device.confirmed:
            return Response({"detail": "Two-factor authentication is already enabled."}, status=409)
        label = f"TaskCraft:{request.user.email}"
        return Response({"provisioning_uri": f"otpauth://totp/{label}?secret={device.secret}&issuer=TaskCraft&algorithm=SHA1&digits=6&period=30"})


class TOTPConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TOTPConfirmSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        try:
            device = TOTPDevice.objects.get(user=request.user)
        except TOTPDevice.DoesNotExist:
            raise serializers.ValidationError({"detail": "Start enrollment first."})
        if not verify_code(device.secret, serializer.validated_data["code"]):
            raise serializers.ValidationError({"code": "Invalid authentication code."})
        device.confirmed = True; device.save(update_fields=["confirmed"])
        return Response(status=204)


class RecoveryCodeGenerationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        codes = generate_recovery_codes()
        RecoveryCode.objects.filter(user=request.user, used_at__isnull=True).delete()
        RecoveryCode.objects.bulk_create([RecoveryCode(user=request.user, code_hash=make_password(code)) for code in codes])
        return Response({"codes": codes})


class RecoveryCodeVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecoveryCodeSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        from django.utils import timezone
        for recovery in RecoveryCode.objects.filter(user=request.user, used_at__isnull=True):
            if check_password(serializer.validated_data["code"], recovery.code_hash):
                recovery.used_at = timezone.now(); recovery.save(update_fields=["used_at"])
                return Response(status=204)
        raise serializers.ValidationError({"code": "Invalid recovery code."})
