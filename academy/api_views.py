import json

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import Enrollment, LearningPath, Lesson, LessonProgress, LabProgress


def user_data(user):
    return {
        "id": user.id,
        "username": user.get_username(),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


def unauthorized():
    return JsonResponse(
        {"authenticated": False, "error": "Authentication required."},
        status=401,
    )


@ensure_csrf_cookie
@require_GET
def csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})


@require_POST
def student_api_login(request):
    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    identifier = str(data.get("username", data.get("email", ""))).strip()
    password = data.get("password", "")

    if not identifier or not isinstance(password, str) or not password:
        return JsonResponse(
            {"error": "Username/email and password are required."},
            status=400,
        )

    User = get_user_model()
    username = identifier

    if "@" in identifier:
        matches = User.objects.filter(email__iexact=identifier)
        if matches.count() == 1:
            username = matches.first().get_username()

    user = authenticate(request, username=username, password=password)

    if user is None:
        return JsonResponse(
            {"error": "Invalid username/email or password."},
            status=401,
        )

    login(request, user)

    return JsonResponse({
        "authenticated": True,
        "user": user_data(user),
        "csrfToken": get_token(request),
    })


@require_POST
def student_api_logout(request):
    logout(request)
    return JsonResponse({
        "authenticated": False,
        "csrfToken": get_token(request),
    })


@require_GET
def student_api_me(request):
    if not request.user.is_authenticated:
        return unauthorized()

    return JsonResponse({
        "authenticated": True,
        "user": user_data(request.user),
    })


@require_POST
def student_api_enroll(request, path_id):
    if not request.user.is_authenticated:
        return unauthorized()

    path = get_object_or_404(
        LearningPath,
        pk=path_id,
        is_published=True,
    )

    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user,
        learning_path=path,
    )

    return JsonResponse({
        "enrolled": True,
        "created": created,
        "learning_path_id": path.id,
        "title": path.title,
    }, status=201 if created else 200)


@require_GET
def student_api_progress(request):
    if not request.user.is_authenticated:
        return unauthorized()

    lessons = Lesson.objects.filter(
        course__learning_paths__enrollments__student=request.user,
        is_published=True,
    ).distinct()

    completed_ids = list(
        LessonProgress.objects.filter(
            student=request.user,
            lesson__in=lessons,
            completed=True,
        ).values_list("lesson_id", flat=True)
    )

    total = lessons.count()
    completed = len(completed_ids)

    return JsonResponse({
        "total_lessons": total,
        "completed_lessons": completed,
        "percent": round(completed / total * 100) if total else 0,
        "completed_lesson_ids": completed_ids,
    })


@require_POST
def student_api_complete_lesson(request, lesson_id):
    if not request.user.is_authenticated:
        return unauthorized()

    lesson = get_object_or_404(
        Lesson,
        pk=lesson_id,
        is_published=True,
    )

    enrolled = Enrollment.objects.filter(
        student=request.user,
        learning_path__courses=lesson.course,
    ).exists()

    if not enrolled:
        return JsonResponse(
            {"error": "You must enrol before completing this lesson."},
            status=403,
        )

    progress, created = LessonProgress.objects.get_or_create(
        student=request.user,
        lesson=lesson,
    )

    if not progress.completed:
        progress.completed = True
        progress.completed_at = timezone.now()
        progress.save(update_fields=["completed", "completed_at"])

    return JsonResponse({
        "completed": True,
        "lesson_id": lesson.id,
        "created": created,
    })


LAB_COURSE_IDS = {
    "terminal",
    "network",
    "web",
    "linux-files",
    "dns-basics",
    "http-status",
    "password-hygiene",
    "incident-triage",
    "mfa-basics",
    "linux-permissions",
    "network-ports",
    "linux-permissions-practice",
    "linux-ownership-practice",
    "dns-records-practice",
    "http-security-headers",
    "ctf-network-wireshark",
    "ctf-linux-hidden-file",
    "ctf-web-phishing",
}


@require_http_methods(["GET", "POST"])
def student_api_lab_progress(request):
    if not request.user.is_authenticated:
        return unauthorized()

    if request.method == "GET":
        records = LabProgress.objects.filter(
            student=request.user
        ).order_by("course_id")

        progress = [
            {
                "course_id": item.course_id,
                "completed": item.completed,
                "quiz_score": item.quiz_score,
                "updated_at": item.updated_at.isoformat(),
            }
            for item in records
        ]

        return JsonResponse({
            "progress": progress,
            "completed_course_ids": [
                item["course_id"]
                for item in progress
                if item["completed"]
            ],
        })

    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    course_id = data.get("course_id")
    completed = data.get("completed", True)
    quiz_score = data.get("quiz_score")

    if course_id not in LAB_COURSE_IDS:
        return JsonResponse({"error": "Unknown lab or CTF ID."}, status=400)

    if not isinstance(completed, bool):
        return JsonResponse({"error": "completed must be true or false."}, status=400)

    if quiz_score is not None and (
        not isinstance(quiz_score, int)
        or isinstance(quiz_score, bool)
        or not 0 <= quiz_score <= 100
    ):
        return JsonResponse({"error": "quiz_score must be between 0 and 100."}, status=400)

    record, created = LabProgress.objects.update_or_create(
        student=request.user,
        course_id=course_id,
        defaults={
            "completed": completed,
            "quiz_score": quiz_score,
            "updated_at": timezone.now(),
        },
    )

    return JsonResponse({
        "saved": True,
        "created": created,
        "course_id": record.course_id,
        "completed": record.completed,
        "quiz_score": record.quiz_score,
    }, status=201 if created else 200)
