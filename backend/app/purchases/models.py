import uuid
from django.conf import settings
from django.db import models


class Purchase(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="purchases", on_delete=models.CASCADE)
    course = models.ForeignKey("courses.Course", related_name="purchases", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    amount = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "course")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} -> {self.course_id} ({self.status})"
