
import json
import logging
import os
import urllib.request
import uuid

from django.db.models import F
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .auth import authenticated_supabase_user
from .models import TrialUsage

logger = logging.getLogger(__name__)

QWEN_API_URL = os.environ.get(
    "QWEN_API_URL",
    "https://ws-tirwz9lb10m6kwaw.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions",
)

QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen3.8-27b")
QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "").strip()

JOSH_INSTRUCTIONS = """You are Josh, the friendly AI cybersecurity tutor for CyberLearn.
Teach beginners in simple language, step by step.
Use practical examples and encourage students.
Give hints before revealing lab answers.
Promote safe, legal and ethical cybersecurity.
Never help attack real systems, steal credentials or deploy malware.
Keep answers focused and easy to understand.
"""


@csrf_exempt
@require_POST
def chat(request):
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

    message = data.get("message", "")
    if not isinstance(message, str):
        return JsonResponse({"error": "Invalid request."}, status=400)

    message = message.strip()
    if not message or len(message) > 2000:
        return JsonResponse(
            {"error": "Message must contain 1–2000 characters."},
            status=400,
        )

    usage, _ = TrialUsage.objects.get_or_create(
        supabase_user_id=user_id,
        defaults={"session_key": uuid.uuid4().hex},
    )

    if not usage.paid_access:
        updated = TrialUsage.objects.filter(
            pk=usage.pk,
            prompts_used__lt=3,
            paid_access=False,
        ).update(prompts_used=F("prompts_used") + 1)

        if updated == 0:
            usage.refresh_from_db()
            if not usage.paid_access:
                return JsonResponse(
                    {
                        "error": "Your 3 free Josh prompts have been used.",
                        "prompts_remaining": 0,
                    },
                    status=429,
                )

    try:
        if not QWEN_API_KEY:
            raise RuntimeError("QWEN_API_KEY is not configured.")

        body = json.dumps({
            "model": QWEN_MODEL,
            "messages": [
                {"role": "system", "content": JOSH_INSTRUCTIONS},
                {"role": "user", "content": message},
            ],
            "stream": False,
            "temperature": 0.6,
            "max_tokens": 700,
        }).encode("utf-8")

        req = urllib.request.Request(
            QWEN_API_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {QWEN_API_KEY}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

        answer = result["choices"][0]["message"]["content"]

        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("Qwen returned an empty response.")

    except Exception:
        logger.exception("Josh Qwen request failed")

        if not usage.paid_access:
            TrialUsage.objects.filter(
                pk=usage.pk,
                prompts_used__gt=0,
            ).update(prompts_used=F("prompts_used") - 1)

        return JsonResponse(
            {"error": "Josh is temporarily unavailable. Please try again."},
            status=502,
        )

    usage.refresh_from_db()

    return JsonResponse({
        "reply": answer,
        "prompts_used": usage.prompts_used,
        "prompts_remaining": (
            None if usage.paid_access else max(0, 3 - usage.prompts_used)
        ),
    })
