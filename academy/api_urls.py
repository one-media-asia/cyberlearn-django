from django.urls import path
from . import api_views, account_api

urlpatterns = [
    path("auth/register/", account_api.register, name="api-register"),
    path("auth/verify-email/", account_api.verify_email, name="api-verify-email"),
    path("auth/password-reset/", account_api.password_reset_request, name="api-password-reset"),
    path("auth/password-reset/confirm/", account_api.password_reset_confirm, name="api-password-reset-confirm"),

    path("student/lab-progress/", api_views.student_api_lab_progress, name="api-lab-progress"),

    path("auth/csrf/", api_views.csrf_token, name="api-csrf"),
    path("auth/login/", api_views.student_api_login, name="api-login"),
    path("auth/logout/", api_views.student_api_logout, name="api-logout"),
    path("auth/me/", api_views.student_api_me, name="api-me"),
    path("student/progress/", api_views.student_api_progress, name="api-progress"),
    path(
        "student/learning-paths/<int:path_id>/enroll/",
        api_views.student_api_enroll,
        name="api-enroll",
    ),
    path(
        "student/lessons/<int:lesson_id>/complete/",
        api_views.student_api_complete_lesson,
        name="api-complete-lesson",
    ),
]
