from django.contrib import admin

from .models import (
    EntranceQuizAttempt,
    EntranceQuizBenefitClaim,
    EntranceQuizConfig,
    EntranceQuizGlobalAttempt,
    EntranceQuizOption,
    EntranceQuizQuestion,
    EntranceQuizReward,
    FreeCourseCompletionBenefitClaim,
    FreeCourseCompletionBenefitConfig,
)


class EntranceQuizOptionInline(admin.TabularInline):
    model = EntranceQuizOption
    extra = 1
    fields = ("text", "is_correct", "order")


@admin.register(EntranceQuizConfig)
class EntranceQuizConfigAdmin(admin.ModelAdmin):
    list_display = ("pass_score", "max_attempts", "discount_percent", "reward_ttl_hours", "is_active", "updated_at")

    def has_add_permission(self, request):
        if EntranceQuizConfig.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(EntranceQuizQuestion)
class EntranceQuizQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "text", "order", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("text",)
    inlines = [EntranceQuizOptionInline]


@admin.register(EntranceQuizAttempt)
class EntranceQuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "course",
        "attempt_no",
        "score_percent",
        "passed",
        "started_at",
        "submitted_at",
    )
    list_filter = ("passed", "course")
    search_fields = ("user__email", "course__title")
    readonly_fields = (
        "id",
        "user",
        "course",
        "attempt_no",
        "question_ids",
        "selected_answers",
        "correct_count",
        "score_percent",
        "passed",
        "started_at",
        "submitted_at",
    )
    actions = ["reset_attempts_for_selected_pairs"]

    @admin.action(description="Reset attempts for selected user-course pairs")
    def reset_attempts_for_selected_pairs(self, request, queryset):
        pairs = set(queryset.values_list("user_id", "course_id"))
        deleted_attempts = 0
        for user_id, course_id in pairs:
            deleted_attempts += EntranceQuizAttempt.objects.filter(user_id=user_id, course_id=course_id).count()
            EntranceQuizAttempt.objects.filter(user_id=user_id, course_id=course_id).delete()
        self.message_user(request, f"Deleted {deleted_attempts} attempts across {len(pairs)} pair(s)")


@admin.register(EntranceQuizReward)
class EntranceQuizRewardAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "course",
        "reward_kind",
        "source_course",
        "percent_off",
        "is_active",
        "expires_at",
        "created_at",
    )
    list_filter = ("is_active", "reward_kind", "course")
    search_fields = ("user__email", "course__title", "source_course__title")
    actions = ["deactivate_rewards", "reset_attempts_for_selected_pairs"]

    @admin.action(description="Deactivate selected rewards")
    def deactivate_rewards(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} reward(s)")

    @admin.action(description="Reset attempts for selected user-course pairs")
    def reset_attempts_for_selected_pairs(self, request, queryset):
        pairs = set(queryset.values_list("user_id", "course_id"))
        deleted_attempts = 0
        for user_id, course_id in pairs:
            deleted_attempts += EntranceQuizAttempt.objects.filter(user_id=user_id, course_id=course_id).count()
            EntranceQuizAttempt.objects.filter(user_id=user_id, course_id=course_id).delete()
        self.message_user(request, f"Deleted {deleted_attempts} attempts across {len(pairs)} pair(s)")


@admin.register(FreeCourseCompletionBenefitConfig)
class FreeCourseCompletionBenefitConfigAdmin(admin.ModelAdmin):
    list_display = ("source_course", "percent_off", "reward_ttl_hours", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("source_course__title", "source_course__id")


@admin.register(FreeCourseCompletionBenefitClaim)
class FreeCourseCompletionBenefitClaimAdmin(admin.ModelAdmin):
    list_display = ("user", "source_course", "target_course", "reward", "created_at")
    list_filter = ("source_course", "target_course")
    search_fields = ("user__email", "source_course__title", "target_course__title")


@admin.register(EntranceQuizGlobalAttempt)
class EntranceQuizGlobalAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "attempt_no",
        "score_percent",
        "passed",
        "started_at",
        "submitted_at",
    )
    list_filter = ("passed",)
    search_fields = ("user__email",)
    readonly_fields = (
        "id",
        "user",
        "attempt_no",
        "question_ids",
        "selected_answers",
        "correct_count",
        "score_percent",
        "passed",
        "started_at",
        "submitted_at",
    )


@admin.register(EntranceQuizBenefitClaim)
class EntranceQuizBenefitClaimAdmin(admin.ModelAdmin):
    list_display = ("user", "target_course", "reward", "created_at")
    search_fields = ("user__email", "target_course__title")
