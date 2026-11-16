from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from rest_framework import generics

from .models import Course, LearningPath, Lesson, Enrollment, LessonProgress
from .serializers import CourseSerializer


def learning_paths(request):
    paths = LearningPath.objects.filter(
        is_published=True
    ).prefetch_related("courses")

    enrolled_ids = set()

    if request.user.is_authenticated:
        enrolled_ids = set(
            Enrollment.objects.filter(
                student=request.user
            ).values_list("learning_path_id", flat=True)
        )

    return render(request, "academy/learning_paths.html", {
        "paths": paths,
        "enrolled_ids": enrolled_ids,
    })


def learning_path_detail(request, path_id):
    path = get_object_or_404(
        LearningPath,
        pk=path_id,
        is_published=True,
    )

    is_enrolled = (
        request.user.is_authenticated
        and Enrollment.objects.filter(
            student=request.user,
            learning_path=path,
        ).exists()
    )

    return render(request, "academy/learning_path_detail.html", {
        "path": path,
        "is_enrolled": is_enrolled,
    })


def student_login(request):
    if request.user.is_authenticated:
        return redirect("student_dashboard")

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )

        if user is not None:
            login(request, user)
            messages.success(request, "Welcome back.")
            return redirect("student_dashboard")

        messages.error(request, "Invalid username or password.")

    return render(request, "academy/login.html")
def student_logout(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("learning_paths")


@login_required(login_url="student_login")
@require_POST
def enroll_learning_path(request, path_id):
    path = get_object_or_404(
        LearningPath,
        pk=path_id,
        is_published=True,
    )

    Enrollment.objects.get_or_create(
        student=request.user,
        learning_path=path,
    )

    messages.success(request, "You are enrolled in this Learning Path.")
    return redirect("learning_path_detail", path_id=path.id)


@login_required(login_url="student_login")
def student_dashboard(request):
    enrollments = Enrollment.objects.filter(
        student=request.user
    ).select_related("learning_path")

    dashboard_items = []

    for enrollment in enrollments:
        path = enrollment.learning_path

        lessons = Lesson.objects.filter(
            course__learning_paths=path,
            is_published=True,
        ).distinct()

        total = lessons.count()

        completed = LessonProgress.objects.filter(
            student=request.user,
            lesson__in=lessons,
            completed=True,
        ).count()

        percent = round(completed / total * 100) if total else 0

        dashboard_items.append({
            "path": path,
            "enrolled_at": enrollment.enrolled_at,
            "total_lessons": total,
            "completed_lessons": completed,
            "percent": percent,
        })

    return render(request, "academy/dashboard.html", {
        "dashboard_items": dashboard_items,
    })


@login_required(login_url="student_login")
@require_POST
def complete_lesson(request, lesson_id):
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
        messages.error(request, "You must enrol first.")
        return redirect("learning_paths")

    progress, created = LessonProgress.objects.get_or_create(
        student=request.user,
        lesson=lesson,
    )

    progress.completed = True
    progress.completed_at = timezone.now()
    progress.save()

    messages.success(request, "Lesson marked as complete.")
    return redirect("student_dashboard")


class CourseListAPIView(generics.ListAPIView):
    serializer_class = CourseSerializer

    def get_queryset(self):
        return Course.objects.filter(
            is_published=True
        ).order_by("title")
from rest_framework import generics
from .models import LearningPath
from .serializers import LearningPathSerializer


class LearningPathListAPIView(generics.ListAPIView):
    queryset = LearningPath.objects.prefetch_related("courses").all()
    serializer_class = LearningPathSerializer


from .serializers import LearningPathSerializer


class LearningPathListAPIView(generics.ListAPIView):
    queryset = LearningPath.objects.prefetch_related("courses").all()
    serializer_class = LearningPathSerializer
