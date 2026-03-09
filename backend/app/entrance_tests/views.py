from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Course

from .models import EntranceQuizAttempt, EntranceQuizGlobalAttempt
from .serializers import (
    EntranceQuizActionSerializer,
    EntranceQuizSubmitSerializer,
    FreeCourseBenefitClaimSerializer,
)
from .services import (
    claim_entrance_quiz_benefit,
    claim_free_course_completion_benefit,
    get_free_course_benefit_status,
    get_unified_quiz_status,
    get_quiz_status,
    start_attempt,
    start_global_attempt,
    submit_global_attempt,
    submit_attempt,
)


class EntranceQuizStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        status_data = get_quiz_status(request.user, course)
        return Response(
            {
                "can_start": status_data.can_start,
                "attempts_used": status_data.attempts_used,
                "attempts_left": status_data.attempts_left,
                "max_attempts": status_data.max_attempts,
                "pass_score": status_data.pass_score,
                "has_active_reward": status_data.has_active_reward,
                "reward_expires_at": status_data.reward_expires_at,
                "discounted_price": status_data.discounted_price,
            }
        )


class EntranceQuizStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        started = start_attempt(request.user, course)
        attempt = started["attempt"]
        return Response(
            {
                "attempt_id": str(attempt.id),
                "attempt_no": attempt.attempt_no,
                "questions": started["questions"],
            }
        )


class EntranceQuizSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(EntranceQuizAttempt, id=attempt_id, user=request.user)

        serializer = EntranceQuizSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = submit_attempt(attempt, serializer.validated_data["answers"])
        reward = result.reward

        response_payload = {
            "passed": result.attempt.passed,
            "score_percent": result.attempt.score_percent,
            "correct_count": result.attempt.correct_count,
            "total_questions": result.total_questions,
            "attempts_left": result.attempts_left,
            "reward": None,
        }

        if reward:
            response_payload["reward"] = {
                "percent_off": reward.percent_off,
                "expires_at": reward.expires_at,
                "is_active": reward.is_active,
            }

        return Response(response_payload)


class EntranceQuizUnifiedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_data = get_unified_quiz_status(request.user)
        return Response(
            {
                "can_start": status_data.can_start,
                "attempts_used": status_data.attempts_used,
                "attempts_left": status_data.attempts_left,
                "max_attempts": status_data.max_attempts,
                "pass_score": status_data.pass_score,
                "has_passed": status_data.has_passed,
                "can_claim": status_data.can_claim,
                "already_claimed": status_data.already_claimed,
                "claimed_target_course": (
                    {
                        "id": status_data.claimed_target_course.id,
                        "title": status_data.claimed_target_course.title,
                    }
                    if status_data.claimed_target_course
                    else None
                ),
            }
        )

    def post(self, request):
        serializer = EntranceQuizActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]

        if action == "start":
            started = start_global_attempt(request.user)
            attempt = started["attempt"]
            return Response(
                {
                    "action": "start",
                    "attempt_id": str(attempt.id),
                    "attempt_no": attempt.attempt_no,
                    "questions": started["questions"],
                }
            )

        if action == "submit":
            attempt = get_object_or_404(
                EntranceQuizGlobalAttempt,
                id=serializer.validated_data["attempt_id"],
                user=request.user,
            )
            result = submit_global_attempt(attempt, serializer.validated_data.get("answers", []))
            return Response(
                {
                    "action": "submit",
                    "passed": result["attempt"].passed,
                    "score_percent": result["attempt"].score_percent,
                    "correct_count": result["attempt"].correct_count,
                    "total_questions": result["total_questions"],
                    "attempts_left": result["attempts_left"],
                }
            )

        target_course = get_object_or_404(Course, id=serializer.validated_data["target_course_id"])
        claim, reward = claim_entrance_quiz_benefit(request.user, target_course)
        return Response(
            {
                "action": "claim",
                "claim_id": str(claim.id),
                "target_course": {
                    "id": target_course.id,
                    "title": target_course.title,
                },
                "reward": {
                    "id": str(reward.id),
                    "percent_off": reward.percent_off,
                    "expires_at": reward.expires_at,
                    "is_active": reward.is_active,
                },
            }
        )


class FreeCourseBenefitStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        source_course = get_object_or_404(Course, id=course_id)
        status_data = get_free_course_benefit_status(request.user, source_course)
        claimed_target = status_data.claimed_target_course
        return Response(
            {
                "is_configured": status_data.is_configured,
                "is_active": status_data.is_active,
                "percent_off": status_data.percent_off,
                "completion_percent": status_data.completion_percent,
                "completed_lessons": status_data.completed_lessons,
                "total_lessons": status_data.total_lessons,
                "is_completed": status_data.is_completed,
                "already_claimed": status_data.already_claimed,
                "can_claim": status_data.can_claim,
                "claimed_target_course": (
                    {
                        "id": claimed_target.id,
                        "title": claimed_target.title,
                    }
                    if claimed_target
                    else None
                ),
                "reward_expires_at": status_data.reward_expires_at,
            }
        )


class FreeCourseBenefitClaimView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        source_course = get_object_or_404(Course, id=course_id)
        serializer = FreeCourseBenefitClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_course = get_object_or_404(Course, id=serializer.validated_data["target_course_id"])

        claim, reward, config = claim_free_course_completion_benefit(
            user=request.user,
            source_course=source_course,
            target_course=target_course,
        )
        return Response(
            {
                "claim_id": str(claim.id),
                "source_course_id": source_course.id,
                "target_course": {
                    "id": target_course.id,
                    "title": target_course.title,
                },
                "percent_off": config.percent_off,
                "reward": {
                    "id": str(reward.id),
                    "percent_off": reward.percent_off,
                    "expires_at": reward.expires_at,
                    "is_active": reward.is_active,
                },
            }
        )
