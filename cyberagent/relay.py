import hmac
import json
import logging
import os
import time
import urllib.request
import urllib.error

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

QWEN_API_URL = os.environ.get(
    "QWEN_API_URL",
    "http://100.122.226.72:11434/api/chat",
)
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen2.5:1.5b")


@csrf_exempt
@require_POST
def chat(request):
    secret = os.environ.get("CYBERAGENT_RELAY_SECRET", "")
    supplied = request.headers.get("X-CyberAgent-Relay-Key", "")

    if len(secret) < 32:
        return JsonResponse({"error": "Relay is not configured."}, status=503)

    if not supplied or not hmac.compare_digest(secret, supplied):
        return JsonResponse({"error": "Unauthorized."}, status=401)

    if len(request.body) > 65536:
        return JsonResponse({"error": "Request too large."}, status=413)

    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    messages = data.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 20:
        return JsonResponse({"error": "Invalid messages."}, status=400)

    clean_messages = []
    total_chars = 0

    for item in messages:
        if not isinstance(item, dict):
            return JsonResponse({"error": "Invalid message."}, status=400)

        role = item.get("role")
        content = item.get("content")

        if role not in ("system", "user", "assistant"):
            return JsonResponse({"error": "Invalid message role."}, status=400)

        if not isinstance(content, str) or not content.strip():
            return JsonResponse({"error": "Invalid message content."}, status=400)

        total_chars += len(content)
        if len(content) > 12000 or total_chars > 40000:
            return JsonResponse({"error": "Message content too large."}, status=413)

        clean_messages.append({"role": role, "content": content})

    max_tokens = data.get("max_tokens", 700)
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
        return JsonResponse({"error": "Invalid max_tokens."}, status=400)
    max_tokens = max(1, min(max_tokens, 2048))

    temperature = data.get("temperature", 0.6)
    if (
        isinstance(temperature, bool)
        or not isinstance(temperature, (int, float))
        or not 0 <= temperature <= 1.5
    ):
        return JsonResponse({"error": "Invalid temperature."}, status=400)

    payload = {
        "model": QWEN_MODEL,
        "messages": clean_messages,
        "stream": False,
        "options": {
            "temperature": float(temperature),
            "num_predict": max_tokens,
        },
    }

    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            QWEN_API_URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

        answer = result.get("message", {}).get("content", "")
        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("Qwen returned an empty response.")

        prompt_tokens = int(result.get("prompt_eval_count") or 0)
        completion_tokens = int(result.get("eval_count") or 0)

        return JsonResponse({
            "id": "cyberagent-qwen",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": QWEN_MODEL,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        })

    except Exception:
        logger.exception("CyberAgent Qwen relay failed")
        return JsonResponse(
            {"error": "CyberAgent AI is temporarily unavailable."},
            status=502,
        )
