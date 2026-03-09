from dataclasses import dataclass

from django.utils import timezone

from entrance_tests.models import EntranceQuizReward

from .models import UserCourseDiscount


@dataclass
class CoursePriceBreakdown:
    platform_price: int
    reward_price: int | None
    final_price: int
    active_reward: EntranceQuizReward | None


def _apply_individual_discount(base_amount: int, discount: UserCourseDiscount | None) -> int:
    if discount is None:
        return base_amount

    if discount.percent_off is not None:
        amount = base_amount - int(base_amount * discount.percent_off / 100)
    else:
        amount = base_amount - int(discount.amount_off or 0)

    return max(amount, 0)


def _get_active_individual_discount(user_email: str, course):
    now = timezone.now()
    discount = (
        UserCourseDiscount.objects
        .filter(user_email__iexact=user_email, course=course, is_active=True)
        .filter(expires_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if discount is not None:
        return discount

    return (
        UserCourseDiscount.objects
        .filter(user_email__iexact=user_email, course=course, is_active=True, expires_at__gt=now)
        .order_by("-created_at")
        .first()
    )


def get_platform_price(user, course) -> int:
    base_price = int(course.effective_price)
    if course.is_free:
        return 0

    if not user or not getattr(user, "is_authenticated", False):
        return base_price

    discount = _get_active_individual_discount(user.email, course)
    return _apply_individual_discount(base_price, discount)


def get_active_course_rewards(user, course):
    if not user or not getattr(user, "is_authenticated", False):
        return []

    now = timezone.now()
    return list(
        EntranceQuizReward.objects
        .filter(user=user, course=course, is_active=True, expires_at__gt=now)
        .order_by("-created_at")
    )


def get_entrance_price_for_percent(course, percent_off: int) -> int:
    if course.is_free:
        return 0

    original_price = int(course.price or 0)
    if original_price <= 0:
        return int(course.effective_price)

    reward_price = int(original_price * (100 - percent_off) / 100)
    return min(int(course.effective_price), max(reward_price, 0))


def get_entrance_reward_price(course, reward: EntranceQuizReward | None) -> int | None:
    if reward is None:
        return None
    return get_entrance_price_for_percent(course=course, percent_off=reward.percent_off)


def get_course_price_breakdown(user, course) -> CoursePriceBreakdown:
    platform_price = get_platform_price(user=user, course=course)
    rewards = get_active_course_rewards(user=user, course=course)
    combined_percent_off = min(sum(int(reward.percent_off) for reward in rewards), 100)
    reward_price = (
        get_entrance_price_for_percent(course=course, percent_off=combined_percent_off)
        if combined_percent_off > 0
        else None
    )

    final_price = platform_price
    if reward_price is not None:
        final_price = min(platform_price, reward_price)

    return CoursePriceBreakdown(
        platform_price=platform_price,
        reward_price=reward_price,
        final_price=max(final_price, 0),
        active_reward=rewards[0] if rewards else None,
    )


def get_active_entrance_reward(user, course):
    # Backward compatible alias for existing code paths.
    rewards = get_active_course_rewards(user=user, course=course)
    return rewards[0] if rewards else None
