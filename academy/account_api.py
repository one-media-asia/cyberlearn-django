import json

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.http import JsonResponse
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.decorators.http import require_GET, require_POST

User = get_user_model()

FRONTEND_URL = "https://cyberlearn.onemedia.asia"
API_URL = "https://api.onemedia.asia"


def read_json(request):
    try:
        return json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def verification_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{API_URL}/api/academy/auth/verify-email/?uid={uid}&token={token}"

    send_mail(
        "Verify your CyberLearn account",
        f"Welcome to CyberLearn!\n\nVerify your email address using this link:\n{link}\n\nIf you did not register, ignore this email.",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


@require_POST
def register(request):
    data = read_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    first_name = str(data.get("first_name", "")).strip()
    last_name = str(data.get("last_name", "")).strip()

    if not username or not email or not isinstance(password, str) or not password:
        return JsonResponse(
            {"error": "Username, email and password are required."},
            status=400,
        )

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse({"error": "That username is already in use."}, status=409)

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"error": "That email address is already registered."}, status=409)

    user = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        is_active=False,
    )

    try:
        password_validation.validate_password(password, user)
    except ValidationError as error:
        return JsonResponse({"errors": error.messages}, status=400)

    user.set_password(password)
    user.save()

    try:
        verification_email(user)
    except Exception:
        user.delete()
        return JsonResponse(
            {"error": "We could not send the verification email. Please try again."},
            status=503,
        )

    return JsonResponse(
        {"registered": True, "message": "Check your email to verify your account."},
        status=201,
    )


@require_GET
def verify_email(request):
    uid = request.GET.get("uid", "")
    token = request.GET.get("token", "")

    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return JsonResponse({"error": "Invalid verification link."}, status=400)

    if user.is_active:
        return JsonResponse({"verified": True, "message": "Your account is already verified."})

    if not default_token_generator.check_token(user, token):
        return JsonResponse({"error": "This verification link is invalid or expired."}, status=400)

    user.is_active = True
    user.save(update_fields=["is_active"])

    return JsonResponse({"verified": True, "message": "Your email is verified. You can now log in."})


@require_POST
def password_reset_request(request):
    data = read_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    email = str(data.get("email", "")).strip().lower()
    if not email:
        return JsonResponse({"error": "Email address is required."}, status=400)

    user = User.objects.filter(email__iexact=email, is_active=True).first()

    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f"{FRONTEND_URL}/reset-password?uid={uid}&token={token}"

        send_mail(
            "Reset your CyberLearn password",
            f"Use this link to reset your password:\n{link}\n\nIf you did not request this, ignore this email.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )

    return JsonResponse({
        "sent": True,
        "message": "If an active account exists for that email, password-reset instructions have been sent.",
    })


@require_POST
def password_reset_confirm(request):
    data = read_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    uid = data.get("uid", "")
    token = data.get("token", "")
    password = data.get("password", "")

    if not uid or not token or not isinstance(password, str) or not password:
        return JsonResponse({"error": "Reset link and new password are required."}, status=400)

    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return JsonResponse({"error": "Invalid or expired reset link."}, status=400)

    if not default_token_generator.check_token(user, token):
        return JsonResponse({"error": "Invalid or expired reset link."}, status=400)

    try:
        password_validation.validate_password(password, user)
    except ValidationError as error:
        return JsonResponse({"errors": error.messages}, status=400)

    user.set_password(password)
    user.save(update_fields=["password"])

    return JsonResponse({"reset": True, "message": "Your password has been updated."})
