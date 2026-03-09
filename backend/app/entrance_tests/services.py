from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from courses.models import Course
from purchases.pricing import get_entrance_price_for_percent, get_platform_price
from progress.models import UserLessonProgress
from purchases.models import Purchase

from .models import (
    EntranceQuizAttempt,
    EntranceQuizBenefitClaim,
    EntranceQuizConfig,
    EntranceQuizGlobalAttempt,
    EntranceQuizQuestion,
    EntranceQuizReward,
    FreeCourseCompletionBenefitClaim,
    FreeCourseCompletionBenefitConfig,
)


@dataclass
class EntranceQuizStatus:
    can_start: bool
    attempts_used: int
    attempts_left: int
    max_attempts: int
    pass_score: int
    has_active_reward: bool
    reward_expires_at: Any
    discounted_price: int


@dataclass
class EntranceQuizSubmitResult:
    attempt: EntranceQuizAttempt
    reward: EntranceQuizReward | None
    total_questions: int
    attempts_left: int


@dataclass
class FreeCourseBenefitStatus:
    is_configured: bool
    is_active: bool
    percent_off: int | None
    completion_percent: int
    completed_lessons: int
    total_lessons: int
    is_completed: bool
    already_claimed: bool
    can_claim: bool
    claimed_target_course: Course | None
    reward_expires_at: Any


@dataclass
class EntranceQuizUnifiedStatus:
    can_start: bool
    attempts_used: int
    attempts_left: int
    max_attempts: int
    pass_score: int
    has_passed: bool
    can_claim: bool
    already_claimed: bool
    claimed_target_course: Course | None


def _require_paid_course(course: Course):
    if course.is_free:
        raise ValidationError("Entrance test is available for paid courses only")
    if not course.price or course.price <= 0:
        raise ValidationError("Course price is not set")


def _require_free_course(course: Course):
    if not course.is_free:
        raise ValidationError("Benefit is available for free courses only")


def _get_course_completion_stats(user, course: Course):
    total_lessons = (
        course.modules
        .aggregate(total=Count("lessons", distinct=True))
        .get("total", 0)
    ) or 0
    completed_lessons = (
        UserLessonProgress.objects
        .filter(user=user, lesson__module__course=course, is_completed=True)
        .values("lesson_id")
        .distinct()
        .count()
    )
    completion_percent = int((completed_lessons / total_lessons) * 100) if total_lessons else 0
    is_completed = bool(total_lessons > 0 and completed_lessons >= total_lessons)
    return {
        "completed_lessons": completed_lessons,
        "total_lessons": total_lessons,
        "completion_percent": min(completion_percent, 100),
        "is_completed": is_completed,
    }


def _get_active_questions():
    return (
        EntranceQuizQuestion.objects
        .filter(is_active=True)
        .prefetch_related("options")
        .order_by("order", "id")
    )


def _build_questions_payload(questions):
    payload = []
    for question in questions:
        options = list(question.options.all())
        if not options:
            continue
        payload.append(
            {
                "id": question.id,
                "text": question.text,
                "options": [
                    {
                        "id": option.id,
                        "text": option.text,
                        "order": option.order,
                    }
                    for option in options
                ],
            }
        )
    return payload


def _global_attempts_queryset(user):
    return EntranceQuizGlobalAttempt.objects.filter(user=user)


def _evaluate_attempt_answers(question_ids: list[int], answers: list[dict[str, int]]):
    questions = list(
        EntranceQuizQuestion.objects
        .filter(id__in=question_ids)
        .prefetch_related("options")
    )
    questions_map = {question.id: question for question in questions}
    provided_map = {int(item["question_id"]): int(item["option_id"]) for item in answers}

    correct_count = 0
    for question_id in question_ids:
        question = questions_map.get(question_id)
        if not question:
            continue
        correct_option = next((opt for opt in question.options.all() if opt.is_correct), None)
        selected_option_id = provided_map.get(question_id)
        if correct_option and selected_option_id == correct_option.id:
            correct_count += 1

    return correct_count, provided_map


def get_active_reward(user, course):
    now = timezone.now()
    return (
        EntranceQuizReward.objects
        .filter(user=user, course=course, is_active=True, expires_at__gt=now)
        .order_by("-created_at")
        .first()
    )


def get_unified_quiz_status(user) -> EntranceQuizUnifiedStatus:
    config = EntranceQuizConfig.get_solo()
    attempts_used = _global_attempts_queryset(user).count()
    attempts_left = max(config.max_attempts - attempts_used, 0)
    has_passed = _global_attempts_queryset(user).filter(passed=True).exists()
    claim = (
        EntranceQuizBenefitClaim.objects
        .filter(user=user)
        .select_related("target_course")
        .first()
    )
    already_claimed = claim is not None
    can_claim = bool(has_passed and not already_claimed)
    can_start = bool(config.is_active and attempts_left > 0 and not has_passed)

    return EntranceQuizUnifiedStatus(
        can_start=can_start,
        attempts_used=attempts_used,
        attempts_left=attempts_left,
        max_attempts=config.max_attempts,
        pass_score=config.pass_score,
        has_passed=has_passed,
        can_claim=can_claim,
        already_claimed=already_claimed,
        claimed_target_course=claim.target_course if claim else None,
    )


@transaction.atomic
def start_global_attempt(user):
    config = EntranceQuizConfig.get_solo()
    if not config.is_active:
        raise ValidationError("Entrance test is currently disabled")

    status = get_unified_quiz_status(user)
    if status.has_passed:
        raise ValidationError("Entrance test already passed")
    if status.attempts_left <= 0:
        raise ValidationError("Attempt limit reached")

    questions = list(_get_active_questions())
    payload = _build_questions_payload(questions)
    if not payload:
        raise ValidationError("Entrance test questions are not configured")

    next_attempt_no = status.attempts_used + 1
    attempt = EntranceQuizGlobalAttempt.objects.create(
        user=user,
        attempt_no=next_attempt_no,
        question_ids=[q["id"] for q in payload],
    )
    return {
        "attempt": attempt,
        "questions": payload,
    }


@transaction.atomic
def submit_global_attempt(attempt: EntranceQuizGlobalAttempt, answers: list[dict[str, int]]):
    if attempt.submitted_at is not None:
        raise ValidationError("Attempt is already submitted")

    config = EntranceQuizConfig.get_solo()
    question_ids = [int(qid) for qid in (attempt.question_ids or [])]
    if not question_ids:
        raise ValidationError("Attempt has no questions")

    correct_count, provided_map = _evaluate_attempt_answers(question_ids, answers)
    total_questions = len(question_ids)
    score_percent = int((correct_count / total_questions) * 100) if total_questions else 0
    passed = score_percent >= config.pass_score

    attempt.selected_answers = {str(k): v for k, v in provided_map.items() if k in question_ids}
    attempt.correct_count = correct_count
    attempt.score_percent = score_percent
    attempt.passed = passed
    attempt.submitted_at = timezone.now()
    attempt.save(
        update_fields=[
            "selected_answers",
            "correct_count",
            "score_percent",
            "passed",
            "submitted_at",
        ]
    )

    attempts_used = _global_attempts_queryset(attempt.user).count()
    attempts_left = max(config.max_attempts - attempts_used, 0)
    return {
        "attempt": attempt,
        "total_questions": total_questions,
        "attempts_left": attempts_left,
    }


@transaction.atomic
def claim_entrance_quiz_benefit(user, target_course: Course):
    if target_course.is_free:
        raise ValidationError("Target course must be paid")
    if not target_course.price or target_course.price <= 0:
        raise ValidationError("Target course price is not set")

    has_passed = _global_attempts_queryset(user).filter(passed=True).exists()
    if not has_passed:
        raise ValidationError("Entrance test must be passed first")

    existing_claim = EntranceQuizBenefitClaim.objects.filter(user=user).first()
    if existing_claim:
        raise ValidationError("Entrance test discount has already been claimed")

    already_paid = Purchase.objects.filter(user=user, course=target_course, status="paid").exists()
    if already_paid:
        raise ValidationError("Target course is already purchased")

    config = EntranceQuizConfig.get_solo()
    now = timezone.now()
    expires_at = now + timedelta(hours=config.reward_ttl_hours)
    reward = EntranceQuizReward.objects.create(
        user=user,
        course=target_course,
        percent_off=config.discount_percent,
        expires_at=expires_at,
        is_active=True,
        reward_kind=EntranceQuizReward.KIND_ENTRANCE_QUIZ,
        source_course=None,
        granted_by_attempt=None,
    )
    claim = EntranceQuizBenefitClaim.objects.create(
        user=user,
        target_course=target_course,
        reward=reward,
    )
    return claim, reward


def get_quiz_status(user, course: Course) -> EntranceQuizStatus:
    _require_paid_course(course)
    config = EntranceQuizConfig.get_solo()

    attempts_used = EntranceQuizAttempt.objects.filter(user=user, course=course).count()
    attempts_left = max(config.max_attempts - attempts_used, 0)
    reward = get_active_reward(user, course)
    platform_price = get_platform_price(user=user, course=course)
    entrance_price = get_entrance_price_for_percent(course=course, percent_off=config.discount_percent)
    discounted_price = min(platform_price, entrance_price)

    can_start = bool(config.is_active and attempts_left > 0 and reward is None)

    return EntranceQuizStatus(
        can_start=can_start,
        attempts_used=attempts_used,
        attempts_left=attempts_left,
        max_attempts=config.max_attempts,
        pass_score=config.pass_score,
        has_active_reward=reward is not None,
        reward_expires_at=reward.expires_at if reward else None,
        discounted_price=discounted_price,
    )


@transaction.atomic
def start_attempt(user, course: Course):
    _require_paid_course(course)
    config = EntranceQuizConfig.get_solo()
    if not config.is_active:
        raise ValidationError("Entrance test is currently disabled")

    if get_active_reward(user, course):
        raise ValidationError("Active entrance reward already exists for this course")

    attempts_used = EntranceQuizAttempt.objects.select_for_update().filter(user=user, course=course).count()
    if attempts_used >= config.max_attempts:
        raise ValidationError("Attempt limit reached")

    questions = list(_get_active_questions())
    payload = _build_questions_payload(questions)
    if not payload:
        raise ValidationError("Entrance test questions are not configured")

    attempt = EntranceQuizAttempt.objects.create(
        user=user,
        course=course,
        attempt_no=attempts_used + 1,
        question_ids=[q["id"] for q in payload],
    )

    return {
        "attempt": attempt,
        "questions": payload,
    }


@transaction.atomic
def submit_attempt(attempt: EntranceQuizAttempt, answers: list[dict[str, int]]) -> EntranceQuizSubmitResult:
    if attempt.submitted_at is not None:
        raise ValidationError("Attempt is already submitted")

    config = EntranceQuizConfig.get_solo()
    question_ids = [int(qid) for qid in (attempt.question_ids or [])]
    if not question_ids:
        raise ValidationError("Attempt has no questions")

    correct_count, provided_map = _evaluate_attempt_answers(question_ids, answers)

    total_questions = len(question_ids)
    score_percent = int((correct_count / total_questions) * 100) if total_questions else 0
    passed = score_percent >= config.pass_score

    now = timezone.now()
    attempt.selected_answers = {str(k): v for k, v in provided_map.items() if k in question_ids}
    attempt.correct_count = correct_count
    attempt.score_percent = score_percent
    attempt.passed = passed
    attempt.submitted_at = now
    attempt.save(
        update_fields=[
            "selected_answers",
            "correct_count",
            "score_percent",
            "passed",
            "submitted_at",
        ]
    )

    reward = None
    if passed:
        expires_at = now + timedelta(hours=config.reward_ttl_hours)
        reward, created = EntranceQuizReward.objects.get_or_create(
            user=attempt.user,
            course=attempt.course,
            reward_kind=EntranceQuizReward.KIND_ENTRANCE_QUIZ,
            defaults={
                "percent_off": config.discount_percent,
                "expires_at": expires_at,
                "is_active": True,
                "reward_kind": EntranceQuizReward.KIND_ENTRANCE_QUIZ,
                "source_course": None,
                "granted_by_attempt": attempt,
            },
        )
        if not created:
            reward.percent_off = config.discount_percent
            reward.expires_at = expires_at
            reward.is_active = True
            reward.reward_kind = EntranceQuizReward.KIND_ENTRANCE_QUIZ
            reward.source_course = None
            reward.granted_by_attempt = attempt
            reward.save(
                update_fields=[
                    "percent_off",
                    "expires_at",
                    "is_active",
                    "reward_kind",
                    "source_course",
                    "granted_by_attempt",
                ]
            )

    attempts_used = EntranceQuizAttempt.objects.filter(user=attempt.user, course=attempt.course).count()
    attempts_left = max(config.max_attempts - attempts_used, 0)

    return EntranceQuizSubmitResult(
        attempt=attempt,
        reward=reward,
        total_questions=total_questions,
        attempts_left=attempts_left,
    )


def get_free_course_benefit_status(user, source_course: Course) -> FreeCourseBenefitStatus:
    _require_free_course(source_course)
    config = (
        FreeCourseCompletionBenefitConfig.objects
        .filter(source_course=source_course)
        .first()
    )
    claim = (
        FreeCourseCompletionBenefitClaim.objects
        .filter(user=user, source_course=source_course)
        .select_related("target_course", "reward")
        .first()
    )
    completion = _get_course_completion_stats(user=user, course=source_course)
    can_claim = bool(
        config
        and config.is_active
        and completion["is_completed"]
        and claim is None
    )
    reward_expires_at = claim.reward.expires_at if claim and claim.reward else None

    return FreeCourseBenefitStatus(
        is_configured=bool(config),
        is_active=bool(config.is_active) if config else False,
        percent_off=config.percent_off if config else None,
        completion_percent=completion["completion_percent"],
        completed_lessons=completion["completed_lessons"],
        total_lessons=completion["total_lessons"],
        is_completed=completion["is_completed"],
        already_claimed=claim is not None,
        can_claim=can_claim,
        claimed_target_course=claim.target_course if claim else None,
        reward_expires_at=reward_expires_at,
    )


@transaction.atomic
def claim_free_course_completion_benefit(user, source_course: Course, target_course: Course):
    _require_free_course(source_course)

    config = (
        FreeCourseCompletionBenefitConfig.objects
        .select_for_update()
        .filter(source_course=source_course, is_active=True)
        .first()
    )
    if not config:
        raise ValidationError("Benefit for this source course is not configured")

    if source_course.id == target_course.id:
        raise ValidationError("Target course must be different from source course")
    if target_course.is_free:
        raise ValidationError("Target course must be paid")
    if not target_course.price or target_course.price <= 0:
        raise ValidationError("Target course price is not set")

    completion = _get_course_completion_stats(user=user, course=source_course)
    if not completion["is_completed"]:
        raise ValidationError("Source course must be completed at 100%")

    claim_exists = FreeCourseCompletionBenefitClaim.objects.filter(
        user=user,
        source_course=source_course,
    ).exists()
    if claim_exists:
        raise ValidationError("Benefit has already been claimed for this source course")

    already_paid = Purchase.objects.filter(
        user=user,
        course=target_course,
        status="paid",
    ).exists()
    if already_paid:
        raise ValidationError("Target course is already purchased")

    now = timezone.now()

    expires_at = (
        now + timedelta(hours=config.reward_ttl_hours)
        if config.reward_ttl_hours > 0
        else now + timedelta(days=3650)
    )

    reward, created = EntranceQuizReward.objects.get_or_create(
        user=user,
        course=target_course,
        reward_kind=EntranceQuizReward.KIND_FREE_COURSE_COMPLETION,
        defaults={
            "percent_off": config.percent_off,
            "expires_at": expires_at,
            "is_active": True,
            "reward_kind": EntranceQuizReward.KIND_FREE_COURSE_COMPLETION,
            "source_course": source_course,
            "granted_by_attempt": None,
        },
    )
    if not created:
        reward.percent_off = config.percent_off
        reward.expires_at = expires_at
        reward.is_active = True
        reward.reward_kind = EntranceQuizReward.KIND_FREE_COURSE_COMPLETION
        reward.source_course = source_course
        reward.granted_by_attempt = None
        reward.save(
            update_fields=[
                "percent_off",
                "expires_at",
                "is_active",
                "reward_kind",
                "source_course",
                "granted_by_attempt",
            ]
        )

    claim = FreeCourseCompletionBenefitClaim.objects.create(
        user=user,
        source_course=source_course,
        target_course=target_course,
        reward=reward,
    )
    return claim, reward, config
