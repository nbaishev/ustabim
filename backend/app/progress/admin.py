from django.contrib import admin
from .models import UserLessonProgress


@admin.register(UserLessonProgress)
class UserLessonProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "lesson", "is_completed", "completed_at")
    list_filter = ("is_completed",)
    search_fields = ("user__email", "lesson__title")
