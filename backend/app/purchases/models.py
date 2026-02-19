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


class UserCourseDiscount(models.Model):
    user_email = models.EmailField()
    course = models.ForeignKey("courses.Course", related_name="user_discounts", on_delete=models.CASCADE)
    percent_off = models.PositiveSmallIntegerField(blank=True, null=True)
    amount_off = models.PositiveIntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user_email", "course")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_email} -> {self.course_id}"

    def clean(self):
        from django.core.exceptions import ValidationError

        has_percent = self.percent_off is not None
        has_amount = self.amount_off is not None
        if has_percent == has_amount:
            raise ValidationError("Exactly one of percent_off or amount_off must be set")

        if self.percent_off is not None and not (1 <= self.percent_off <= 100):
            raise ValidationError("percent_off must be in range 1..100")
