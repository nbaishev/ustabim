from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from courses.models import Course
from entrance_tests.models import EntranceQuizConfig, EntranceQuizGlobalAttempt, EntranceQuizOption, EntranceQuizQuestion
from users.models import User


def auth_headers(user):
    token = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class EntranceQuizUnifiedTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="unified@example.com", password="pass", name="Unified User")
        self.target_course = Course.objects.create(
            id="target-paid",
            title="Target Paid",
            description="Paid",
            full_description="Paid",
            is_free=False,
            price=1000,
            level="Средний",
        )

        EntranceQuizConfig.objects.create(
            pass_score=70,
            max_attempts=2,
            discount_percent=50,
            reward_ttl_hours=72,
            is_active=True,
        )

        q1 = EntranceQuizQuestion.objects.create(text="Q1", order=1, is_active=True)
        EntranceQuizOption.objects.create(question=q1, text="Correct", is_correct=True, order=1)
        EntranceQuizOption.objects.create(question=q1, text="Wrong", is_correct=False, order=2)

        q2 = EntranceQuizQuestion.objects.create(text="Q2", order=2, is_active=True)
        EntranceQuizOption.objects.create(question=q2, text="Correct", is_correct=True, order=1)
        EntranceQuizOption.objects.create(question=q2, text="Wrong", is_correct=False, order=2)

    def _entrance_get_status(self):
        url = reverse("entrance-test-unified")
        return self.client.get(url, **auth_headers(self.user))

    def _entrance_start(self):
        url = reverse("entrance-test-unified")
        return self.client.post(url, {"action": "start"}, format="json", **auth_headers(self.user))

    def _entrance_submit(self, attempt_id: str, correct: bool):
        attempt = EntranceQuizGlobalAttempt.objects.get(id=attempt_id)
        answers = []
        for question_id in attempt.question_ids:
            question = EntranceQuizQuestion.objects.get(id=question_id)
            if correct:
                option_id = question.options.get(is_correct=True).id
            else:
                option_id = question.options.filter(is_correct=False).first().id
            answers.append({"question_id": question_id, "option_id": option_id})

        url = reverse("entrance-test-unified")
        return self.client.post(
            url,
            {"action": "submit", "attempt_id": attempt_id, "answers": answers},
            format="json",
            **auth_headers(self.user),
        )

    def _entrance_claim(self, target_course_id: str):
        url = reverse("entrance-test-unified")
        return self.client.post(
            url,
            {"action": "claim", "target_course_id": target_course_id},
            format="json",
            **auth_headers(self.user),
        )

    def test_unified_flow_pass_then_claim(self):
        status_before = self._entrance_get_status()
        self.assertEqual(status_before.status_code, status.HTTP_200_OK)
        self.assertTrue(status_before.data["can_start"])
        self.assertFalse(status_before.data["has_passed"])

        started = self._entrance_start()
        self.assertEqual(started.status_code, status.HTTP_200_OK)

        submitted = self._entrance_submit(started.data["attempt_id"], correct=True)
        self.assertEqual(submitted.status_code, status.HTTP_200_OK)
        self.assertTrue(submitted.data["passed"])

        status_after_pass = self._entrance_get_status()
        self.assertTrue(status_after_pass.data["has_passed"])
        self.assertTrue(status_after_pass.data["can_claim"])

        claimed = self._entrance_claim(self.target_course.id)
        self.assertEqual(claimed.status_code, status.HTTP_200_OK)
        self.assertEqual(claimed.data["target_course"]["id"], self.target_course.id)

        status_after_claim = self._entrance_get_status()
        self.assertTrue(status_after_claim.data["already_claimed"])
        self.assertFalse(status_after_claim.data["can_claim"])

    def test_unified_claim_requires_passed_test(self):
        response = self._entrance_claim(self.target_course.id)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unified_submit_failed_attempt(self):
        started = self._entrance_start()
        submitted = self._entrance_submit(started.data["attempt_id"], correct=False)

        self.assertEqual(submitted.status_code, status.HTTP_200_OK)
        self.assertFalse(submitted.data["passed"])
        self.assertEqual(submitted.data["attempts_left"], 1)
