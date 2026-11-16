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


@csrf_exempt
@require_POST
def trial_start(request):
    try:
        user_id = authenticated_supabase_user(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=401)
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=503)

    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    # Migrate a previously issued paid browser token to this verified account.
    # Unpaid anonymous records are never attached to an account.
    legacy_token = data.get("token", "")
    if isinstance(legacy_token, str) and legacy_token:
        try:
            payload = signing.loads(
                legacy_token,
                salt=TOKEN_SALT,
                max_age=TOKEN_MAX_AGE,
            )
            legacy_usage = TrialUsage.objects.filter(
                session_key=payload["visitor_id"],
                paid_access=True,
            ).first()
        except (signing.BadSignature, KeyError, TypeError):
            legacy_usage = None

        if legacy_usage is not None:
            existing = TrialUsage.objects.filter(supabase_user_id=user_id).first()
            if existing is None and legacy_usage.supabase_user_id is None:
                legacy_usage.supabase_user_id = user_id
                legacy_usage.save(update_fields=["supabase_user_id", "updated_at"])
            elif existing is not None and not existing.paid_access:
                existing.paid_access = True
                existing.save(update_fields=["paid_access", "updated_at"])

    usage = account_usage(user_id)
    remaining = None if usage.paid_access else max(0, 3 - usage.prompts_used)

    return JsonResponse({
        "prompts_used": usage.prompts_used,
        "prompts_remaining": remaining,
        "paid_access": usage.paid_access,
    })
