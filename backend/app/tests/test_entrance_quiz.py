from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from courses.models import Course
from entrance_tests.models import (
    EntranceQuizAttempt,
    EntranceQuizConfig,
    EntranceQuizOption,
    EntranceQuizQuestion,
    EntranceQuizReward,
)
from purchases.models import UserCourseDiscount
from users.models import User


def auth_headers(user):
    token = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class EntranceQuizFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="quiz@example.com", password="pass", name="Quiz User")
        self.course = Course.objects.create(
            id="quiz-course",
            title="Quiz Course",
            description="Paid",
            full_description="Paid",
            is_free=False,
            price=1000,
            discount_price=800,
            level="Средний",
        )
        EntranceQuizConfig.objects.create(
            pass_score=70,
            max_attempts=2,
            discount_percent=50,
            reward_ttl_hours=72,
            is_active=True,
        )

        q1 = EntranceQuizQuestion.objects.create(text="Question 1", order=1, is_active=True)
        EntranceQuizOption.objects.create(question=q1, text="Correct 1", is_correct=True, order=1)
        EntranceQuizOption.objects.create(question=q1, text="Wrong 1", is_correct=False, order=2)

        q2 = EntranceQuizQuestion.objects.create(text="Question 2", order=2, is_active=True)
        EntranceQuizOption.objects.create(question=q2, text="Correct 2", is_correct=True, order=1)
        EntranceQuizOption.objects.create(question=q2, text="Wrong 2", is_correct=False, order=2)

    def _start_attempt(self):
        url = reverse("entrance-test-start", kwargs={"course_id": self.course.id})
        return self.client.post(url, {}, format="json", **auth_headers(self.user))

    def _submit_attempt(self, attempt_id, use_correct_answers: bool):
        attempt = EntranceQuizAttempt.objects.get(id=attempt_id)
        answers = []
        for question_id in attempt.question_ids:
            question = EntranceQuizQuestion.objects.get(id=question_id)
            if use_correct_answers:
                option_id = question.options.get(is_correct=True).id
            else:
                option_id = question.options.filter(is_correct=False).order_by("id").first().id
            answers.append({"question_id": question_id, "option_id": option_id})

        submit_url = reverse("entrance-test-submit", kwargs={"attempt_id": attempt_id})
        return self.client.post(submit_url, {"answers": answers}, format="json", **auth_headers(self.user))

    def _purchase_course(self):
        finik_config = SimpleNamespace(
            api_key="test-key",
            private_key_pem="test-private-pem",
            account_id="test-account",
            merchant_category_code="6012",
            qr_name="Test QR",
            qr_expires_minutes=30,
            webhook_url=None,
        )
        fake_response = Mock()
        fake_response.status_code = 201
        fake_response.headers = {}
        fake_response.json.return_value = {"paymentUrl": "https://pay.test.local/checkout"}
        fake_response.text = ""

        purchase_url = reverse("purchase-list")
        with (
            override_settings(FINIK_REDIRECT_URL="https://academy.local/payment/success"),
            patch("purchases.views.get_config", return_value=finik_config),
            patch("purchases.views.create_payment", return_value=fake_response),
        ):
            return self.client.post(
                purchase_url,
                {"course_id": self.course.id},
                format="json",
                **auth_headers(self.user),
            )

    def test_third_attempt_is_blocked(self):
        first = self._start_attempt()
        second = self._start_attempt()
        third = self._start_attempt()

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(third.status_code, status.HTTP_400_BAD_REQUEST)

    def test_successful_attempt_creates_reward_with_72h_ttl(self):
        start = self._start_attempt()
        self.assertEqual(start.status_code, status.HTTP_200_OK)

        submit = self._submit_attempt(start.data["attempt_id"], use_correct_answers=True)
        self.assertEqual(submit.status_code, status.HTTP_200_OK)
        self.assertTrue(submit.data["passed"])

        reward = EntranceQuizReward.objects.get(user=self.user, course=self.course)
        self.assertEqual(reward.percent_off, 50)
        ttl_hours = (reward.expires_at - timezone.now()).total_seconds() / 3600
        self.assertGreater(ttl_hours, 71)
        self.assertLessEqual(ttl_hours, 72.1)

    def test_failed_attempt_does_not_create_reward(self):
        start = self._start_attempt()
        submit = self._submit_attempt(start.data["attempt_id"], use_correct_answers=False)

        self.assertEqual(submit.status_code, status.HTTP_200_OK)
        self.assertFalse(submit.data["passed"])
        self.assertIsNone(submit.data["reward"])
        self.assertFalse(EntranceQuizReward.objects.filter(user=self.user, course=self.course).exists())

    def test_status_returns_attempts_and_active_reward(self):
        start = self._start_attempt()
        submit = self._submit_attempt(start.data["attempt_id"], use_correct_answers=True)
        self.assertEqual(submit.status_code, status.HTTP_200_OK)

        status_url = reverse("entrance-test-status", kwargs={"course_id": self.course.id})
        response = self.client.get(status_url, **auth_headers(self.user))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["attempts_used"], 1)
        self.assertEqual(response.data["attempts_left"], 1)
        self.assertEqual(response.data["pass_score"], 70)
        self.assertTrue(response.data["has_active_reward"])
        self.assertFalse(response.data["can_start"])
        self.assertEqual(response.data["discounted_price"], 500)

    def test_active_reward_keeps_more_profitable_platform_discount(self):
        EntranceQuizReward.objects.create(
            user=self.user,
            course=self.course,
            percent_off=50,
            expires_at=timezone.now() + timedelta(hours=72),
            is_active=True,
        )
        UserCourseDiscount.objects.create(
            user_email=self.user.email,
            course=self.course,
            percent_off=60,
            is_active=True,
        )

        detail_url = reverse("course-detail", kwargs={"id": self.course.id})
        detail_response = self.client.get(detail_url, **auth_headers(self.user))
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["current_price"], 320)

        purchase_response = self._purchase_course()
        self.assertEqual(purchase_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(purchase_response.data["amount"], 320)

    def test_expired_reward_does_not_affect_price(self):
        EntranceQuizReward.objects.create(
            user=self.user,
            course=self.course,
            percent_off=50,
            expires_at=timezone.now() - timedelta(minutes=1),
            is_active=True,
        )

        detail_url = reverse("course-detail", kwargs={"id": self.course.id})
        detail_response = self.client.get(detail_url, **auth_headers(self.user))

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["current_price"], 800)

    def test_purchase_without_test_is_still_allowed(self):
        response = self._purchase_course()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], 800)

    def test_price_consistency_between_course_and_purchase_with_reward(self):
        EntranceQuizReward.objects.create(
            user=self.user,
            course=self.course,
            percent_off=50,
            expires_at=timezone.now() + timedelta(hours=72),
            is_active=True,
        )

        detail_url = reverse("course-detail", kwargs={"id": self.course.id})
        detail_response = self.client.get(detail_url, **auth_headers(self.user))

        purchase_response = self._purchase_course()

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(purchase_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(detail_response.data["current_price"], purchase_response.data["amount"])
        self.assertEqual(purchase_response.data["amount"], 500)
