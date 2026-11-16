import json
import uuid

from django.core import signing
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .auth import authenticated_supabase_user
from .models import TrialUsage

TOKEN_SALT = "cyberagent.trial.v1"
TOKEN_MAX_AGE = 60 * 60 * 24 * 30


def account_usage(user_id):
    usage, _ = TrialUsage.objects.get_or_create(
        supabase_user_id=user_id,
        defaults={"session_key": uuid.uuid4().hex},
    )
    return usage


def guest_usage(token):
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        visitor_id = payload["visitor_id"]
        if not isinstance(visitor_id, str):
            return None
        return TrialUsage.objects.filter(
            session_key=visitor_id,
            supabase_user_id__isnull=True,
        ).first()
    except (signing.BadSignature, KeyError, TypeError):
        return None


@csrf_exempt
@require_POST
def trial_start(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    authorization = request.headers.get("Authorization", "")

    if authorization.startswith("Bearer "):
        try:
            user_id = authenticated_supabase_user(request)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=401)
        except RuntimeError as exc:
            return JsonResponse({"error": str(exc)}, status=503)

        usage = account_usage(user_id)
        return JsonResponse({
            "prompts_used": usage.prompts_used,
            "prompts_remaining": None,
            "paid_access": True,
        })

    token = data.get("token", "")
    if token:
        if not isinstance(token, str):
            return JsonResponse({"error": "Invalid guest trial token."}, status=400)
        usage = guest_usage(token)
        if usage is None:
            return JsonResponse({"error": "Guest trial token expired or invalid."}, status=401)
    else:
        visitor_id = uuid.uuid4().hex
        usage = TrialUsage.objects.create(session_key=visitor_id)
        token = signing.dumps({"visitor_id": visitor_id}, salt=TOKEN_SALT)

    return JsonResponse({
        "token": token,
        "prompts_used": usage.prompts_used,
        "prompts_remaining": max(0, 3 - usage.prompts_used),
        "paid_access": False,
    })
