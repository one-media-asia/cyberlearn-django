import json
import os
import urllib.error
import urllib.request
import uuid


def authenticated_supabase_user(request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise ValueError("Please sign in to your CyberLearn account.")

    access_token = authorization[7:].strip()
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    publishable_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")

    if not supabase_url or not publishable_key:
        raise RuntimeError("Supabase authentication is not configured.")

    req = urllib.request.Request(
        f"{supabase_url}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": publishable_key,
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            user = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401, 403):
            raise ValueError("Your sign-in has expired. Please sign in again.")
        raise RuntimeError("Could not verify your CyberLearn account.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Supabase authentication is temporarily unavailable.") from exc

    try:
        return uuid.UUID(user["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Supabase returned an invalid account identity.") from exc
