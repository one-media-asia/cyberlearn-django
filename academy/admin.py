from django.contrib import admin
from .models import Course, LearningPath, Lesson, Enrollment, LessonProgress


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "level", "is_published")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("courses",)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order", "is_published")


admin.site.register(Enrollment)
admin.site.register(LessonProgress)
