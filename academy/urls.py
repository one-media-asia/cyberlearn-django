from django.urls import path
from . import views
from .views import LearningPathListAPIView
urlpatterns = [
    path("learning-paths/", LearningPathListAPIView.as_view(), name="learning-path-list"),
    path("", views.learning_paths, name="learning_paths"),
    path("learning-paths/<int:path_id>/", views.learning_path_detail, name="learning_path_detail"),
    path("learning-paths/<int:path_id>/enroll/", views.enroll_learning_path, name="enroll_learning_path"),
    path("login/", views.student_login, name="student_login"),
    path("logout/", views.student_logout, name="student_logout"),
    path("dashboard/", views.student_dashboard, name="student_dashboard"),
    path("lessons/<int:lesson_id>/complete/", views.complete_lesson, name="complete_lesson"),
    path("courses/", views.CourseListAPIView.as_view(), name="course-list"),
]
