import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class EntranceQuizConfig(models.Model):
    singleton_enforcer = models.BooleanField(default=True, unique=True, editable=False)
    pass_score = models.PositiveSmallIntegerField(default=70)
    max_attempts = models.PositiveSmallIntegerField(default=2)
    discount_percent = models.PositiveSmallIntegerField(default=50)
    reward_ttl_hours = models.PositiveIntegerField(default=72)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Entrance Quiz Config"
        verbose_name_plural = "Entrance Quiz Config"

    def __str__(self):
        return "Entrance Quiz Config"

    def clean(self):
        if not (1 <= self.pass_score <= 100):
            raise ValidationError("pass_score must be in range 1..100")
        if self.max_attempts < 1:
            raise ValidationError("max_attempts must be at least 1")
        if not (1 <= self.discount_percent <= 100):
            raise ValidationError("discount_percent must be in range 1..100")
        if self.reward_ttl_hours < 1:
            raise ValidationError("reward_ttl_hours must be at least 1")

    def save(self, *args, **kwargs):
        self.singleton_enforcer = True
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        config = cls.objects.first()
        if config:
            return config
        return cls.objects.create()


class EntranceQuizQuestion(models.Model):
    text = models.TextField()
    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Q{self.id}: {self.text[:40]}"


class EntranceQuizOption(models.Model):
    question = models.ForeignKey(
        EntranceQuizQuestion,
        related_name="options",
        on_delete=models.CASCADE,
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Option {self.id} for Q{self.question_id}"


class EntranceQuizAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="entrance_quiz_attempts",
        on_delete=models.CASCADE,
    )
    course = models.ForeignKey(
        "courses.Course",
        related_name="entrance_quiz_attempts",
        on_delete=models.CASCADE,
    )
    attempt_no = models.PositiveSmallIntegerField()
    question_ids = models.JSONField(default=list, blank=True)
    selected_answers = models.JSONField(default=dict, blank=True)
    correct_count = models.PositiveIntegerField(default=0)
    score_percent = models.PositiveSmallIntegerField(default=0)
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("user", "course", "attempt_no")
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user_id} / {self.course_id} / attempt {self.attempt_no}"


class EntranceQuizReward(models.Model):
    KIND_ENTRANCE_QUIZ = "entrance_quiz"
    KIND_FREE_COURSE_COMPLETION = "free_course_completion"
    REWARD_KIND_CHOICES = (
        (KIND_ENTRANCE_QUIZ, "Entrance Quiz"),
        (KIND_FREE_COURSE_COMPLETION, "Free Course Completion"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="entrance_quiz_rewards",
        on_delete=models.CASCADE,
    )
    course = models.ForeignKey(
        "courses.Course",
        related_name="entrance_quiz_rewards",
        on_delete=models.CASCADE,
    )
    percent_off = models.PositiveSmallIntegerField(default=50)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    reward_kind = models.CharField(
        max_length=32,
        choices=REWARD_KIND_CHOICES,
        default=KIND_ENTRANCE_QUIZ,
    )
    source_course = models.ForeignKey(
        "courses.Course",
        related_name="completion_source_rewards",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    granted_by_attempt = models.ForeignKey(
        EntranceQuizAttempt,
        related_name="granted_rewards",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "course", "reward_kind")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} -> {self.course_id} ({self.percent_off}% off)"

    @property
    def is_valid_now(self) -> bool:
        return self.is_active and self.expires_at > timezone.now()

    def clean(self):
        if not (1 <= self.percent_off <= 100):
            raise ValidationError("percent_off must be in range 1..100")
        if (
            self.reward_kind == self.KIND_FREE_COURSE_COMPLETION
            and self.source_course is None
        ):
            raise ValidationError("source_course is required for free_course_completion reward")


class EntranceQuizGlobalAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="entrance_quiz_global_attempts",
        on_delete=models.CASCADE,
    )
    attempt_no = models.PositiveSmallIntegerField()
    question_ids = models.JSONField(default=list, blank=True)
    selected_answers = models.JSONField(default=dict, blank=True)
    correct_count = models.PositiveIntegerField(default=0)
    score_percent = models.PositiveSmallIntegerField(default=0)
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("user", "attempt_no")
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user_id} / global attempt {self.attempt_no}"


class EntranceQuizBenefitClaim(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="entrance_quiz_benefit_claim",
        on_delete=models.CASCADE,
    )
    target_course = models.ForeignKey(
        "courses.Course",
        related_name="entrance_quiz_benefit_claims",
        on_delete=models.CASCADE,
    )
    reward = models.ForeignKey(
        EntranceQuizReward,
        related_name="entrance_quiz_claims",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} -> {self.target_course_id}"


class FreeCourseCompletionBenefitConfig(models.Model):
    source_course = models.OneToOneField(
        "courses.Course",
        related_name="completion_benefit_config",
        on_delete=models.CASCADE,
    )
    percent_off = models.PositiveSmallIntegerField(default=10)
    reward_ttl_hours = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_course_id"]
        verbose_name = "Free Course Benefit Config"
        verbose_name_plural = "Free Course Benefit Configs"

    def __str__(self):
        return f"{self.source_course_id}: {self.percent_off}%"

    def clean(self):
        if not self.source_course.is_free:
            raise ValidationError("source_course must be free")
        if not (1 <= self.percent_off <= 100):
            raise ValidationError("percent_off must be in range 1..100")


class FreeCourseCompletionBenefitClaim(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="free_course_benefit_claims",
        on_delete=models.CASCADE,
    )
    source_course = models.ForeignKey(
        "courses.Course",
        related_name="free_course_benefit_claims",
        on_delete=models.CASCADE,
    )
    target_course = models.ForeignKey(
        "courses.Course",
        related_name="received_free_course_claims",
        on_delete=models.CASCADE,
    )
    reward = models.ForeignKey(
        EntranceQuizReward,
        related_name="completion_claims",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "source_course")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id}: {self.source_course_id} -> {self.target_course_id}"
