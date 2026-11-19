import json
import logging
import os
import urllib.request
import uuid

from django.core import signing
from django.db.models import F
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .auth import authenticated_supabase_user
from .models import TrialUsage
from .views import TOKEN_MAX_AGE, TOKEN_SALT

logger = logging.getLogger(__name__)

QWEN_API_URL = os.environ.get(
    "QWEN_API_URL",
    "https://ws-tirwz9lb10m6kwaw.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions",
)
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen3.8-27b")
QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "").strip()

JOSH_INSTRUCTIONS = """You are Josh, the friendly AI cybersecurity tutor for CyberLearn.

TEACHING STYLE
- Teach beginners in simple language, step by step.
- Use practical, realistic examples.
- Be conversational and encouraging, never patronising.
- Answer the question actually asked before suggesting follow-up topics.
- Do not anticipate or answer several unasked questions.
- Adapt explanations to the student's demonstrated knowledge.
- Give hints before revealing lab answers.

TECHNICAL ACCURACY
- Accuracy is more important than sounding confident.
- Never invent commands, configuration options, protocols or technical behaviour.
- Distinguish simplified analogies from how technology actually works.
- Explain cryptography, authentication and networking accurately.
- For SSH public-key authentication, explain that the client proves possession of its private key using a digital signature, which the server verifies with the public key.
- Never describe SSH public-key authentication as the server encrypting a secret message for the client to decrypt.
- Clearly identify assumptions, limitations and uncertainty.
- Correct misconceptions politely and explain why they are incorrect.
- Never claim to have tested or executed something you have not actually tested.

CONVERSATION
- Remember and use relevant details from earlier messages.
- Do not ask students to repeat information they have already provided.
- Answer follow-up questions in the context of the previous discussion.
- Respect explicit instructions about length, format and scope.
- If asked for exactly two sentences, provide exactly two sentences.

CYBERSECURITY SAFETY
- Promote safe, legal and ethical cybersecurity.
- Never help attack real systems, steal credentials or deploy malware.
- Keep practical exercises within authorised labs and test environments.
- Explain defensive alternatives when refusing unsafe requests.

RESPONSE FORMAT
- Keep answers focused and easy to understand.
- Use headings and bullet points when they improve clarity.
- Explain technical terms when first introduced.
- Avoid unnecessary repetition and long introductions.
"""


@csrf_exempt
@require_POST
def chat(request):
    authorization = request.headers.get("Authorization", "")
    is_student = authorization.startswith("Bearer ")
    usage = None

    if is_student:
        try:
            user_id = authenticated_supabase_user(request)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=401)
        except RuntimeError as exc:
            return JsonResponse({"error": str(exc)}, status=503)

        usage, _ = TrialUsage.objects.get_or_create(
            supabase_user_id=user_id,
            defaults={"session_key": uuid.uuid4().hex},
        )
    else:
        token = request.headers.get("X-Josh-Trial-Token", "")
        try:
            payload = signing.loads(
                token,
                salt=TOKEN_SALT,
                max_age=TOKEN_MAX_AGE,
            )
            visitor_id = payload["visitor_id"]
            if not isinstance(visitor_id, str):
                raise ValueError("Invalid guest token.")
            usage = TrialUsage.objects.filter(
                session_key=visitor_id,
                supabase_user_id__isnull=True,
            ).first()
        except (signing.BadSignature, KeyError, TypeError, ValueError):
            usage = None

        if usage is None:
            return JsonResponse(
                {"error": "Your guest trial has expired. Please refresh Josh."},
                status=401,
            )

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

    if not is_student:
        updated = TrialUsage.objects.filter(
            pk=usage.pk,
            prompts_used__lt=3,
        ).update(prompts_used=F("prompts_used") + 1)

        if updated == 0:
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

        if not is_student:
            TrialUsage.objects.filter(
                pk=usage.pk,
                prompts_used__gt=0,
            ).update(prompts_used=F("prompts_used") - 1)

        return JsonResponse(
            {"error": "Josh is temporarily unavailable. Please try again."},
            status=502,
        )

    if is_student:
        return JsonResponse({
            "reply": answer,
            "prompts_remaining": None,
        })

    usage.refresh_from_db()
    return JsonResponse({
        "reply": answer,
        "prompts_used": usage.prompts_used,
        "prompts_remaining": max(0, 3 - usage.prompts_used),
    })
