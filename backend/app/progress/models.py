from django.conf import settings
from django.db import models


class UserLessonProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="lesson_progress", on_delete=models.CASCADE)
    lesson = models.ForeignKey("courses.Lesson", related_name="progress_records", on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("user", "lesson")
        ordering = ["-completed_at", "lesson_id"]

    def __str__(self):
        return f"{self.user.email} - {self.lesson_id} ({'done' if self.is_completed else 'pending'})"
