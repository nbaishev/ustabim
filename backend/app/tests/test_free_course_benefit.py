from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from courses.models import Course, Lesson, Module
from entrance_tests.models import (
    EntranceQuizReward,
    FreeCourseCompletionBenefitClaim,
    FreeCourseCompletionBenefitConfig,
)
from users.models import User


def auth_headers(user):
    token = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class FreeCourseBenefitTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="benefit@example.com", password="pass", name="Benefit User")

        self.source_course = Course.objects.create(
            id="bim-basics-free",
            title="BIM Basics Free",
            description="Free",
            full_description="Free",
            is_free=True,
            level="Начинающий",
        )
        source_module = Module.objects.create(course=self.source_course, title="Basics", order=1)
        self.source_lesson_1 = Lesson.objects.create(
            module=source_module,
            title="Intro",
            video_url="https://example.com/intro",
            order=1,
        )
        self.source_lesson_2 = Lesson.objects.create(
            module=source_module,
            title="Modeling",
            video_url="https://example.com/modeling",
            order=2,
        )

        self.target_course = Course.objects.create(
            id="bim-pro-paid",
            title="BIM Pro",
            description="Paid",
            full_description="Paid",
            is_free=False,
            price=1000,
            level="Средний",
        )
        self.alt_target_course = Course.objects.create(
            id="bim-manager-paid",
            title="BIM Manager",
            description="Paid",
            full_description="Paid",
            is_free=False,
            price=2000,
            level="Продвинутый",
        )

        FreeCourseCompletionBenefitConfig.objects.create(
            source_course=self.source_course,
            percent_off=10,
            reward_ttl_hours=0,
            is_active=True,
        )

    def _complete_source_course(self):
        url = reverse("me-progress-complete")
        for lesson in (self.source_lesson_1, self.source_lesson_2):
            response = self.client.post(
                url,
                {"course_id": self.source_course.id, "lesson_id": lesson.id},
                format="json",
                **auth_headers(self.user),
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def _benefit_status(self):
        url = reverse("free-course-benefit-status", kwargs={"course_id": self.source_course.id})
        return self.client.get(url, **auth_headers(self.user))

    def _claim_benefit(self, target_course_id: str):
        url = reverse("free-course-benefit-claim", kwargs={"course_id": self.source_course.id})
        return self.client.post(
            url,
            {"target_course_id": target_course_id},
            format="json",
            **auth_headers(self.user),
        )

    def _purchase_target(self):
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
                {"course_id": self.target_course.id},
                format="json",
                **auth_headers(self.user),
            )

    def test_status_is_not_claimable_before_full_completion(self):
        response = self._benefit_status()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_completed"])
        self.assertFalse(response.data["can_claim"])
        self.assertFalse(response.data["already_claimed"])
        self.assertEqual(response.data["completion_percent"], 0)

    def test_status_becomes_claimable_after_full_completion(self):
        self._complete_source_course()

        response = self._benefit_status()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_completed"])
        self.assertTrue(response.data["can_claim"])
        self.assertEqual(response.data["completion_percent"], 100)
        self.assertEqual(response.data["percent_off"], 10)

    def test_claim_creates_reward_and_applies_price(self):
        self._complete_source_course()

        claim_response = self._claim_benefit(self.target_course.id)
        self.assertEqual(claim_response.status_code, status.HTTP_200_OK)

        reward = EntranceQuizReward.objects.get(user=self.user, course=self.target_course)
        self.assertEqual(reward.percent_off, 10)
        self.assertEqual(reward.reward_kind, EntranceQuizReward.KIND_FREE_COURSE_COMPLETION)
        self.assertEqual(reward.source_course_id, self.source_course.id)

        claim = FreeCourseCompletionBenefitClaim.objects.get(user=self.user, source_course=self.source_course)
        self.assertEqual(claim.target_course_id, self.target_course.id)

        detail_url = reverse("course-detail", kwargs={"id": self.target_course.id})
        detail_response = self.client.get(detail_url, **auth_headers(self.user))
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["current_price"], 900)

        purchase_response = self._purchase_target()
        self.assertEqual(purchase_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(purchase_response.data["amount"], 900)

    def test_claim_is_one_time_per_source_course(self):
        self._complete_source_course()

        first_claim = self._claim_benefit(self.target_course.id)
        second_claim = self._claim_benefit(self.alt_target_course.id)

        self.assertEqual(first_claim.status_code, status.HTTP_200_OK)
        self.assertEqual(second_claim.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            FreeCourseCompletionBenefitClaim.objects.filter(user=self.user, source_course=self.source_course).count(),
            1,
        )

    def test_claim_rejects_free_target_course(self):
        self._complete_source_course()

        response = self._claim_benefit(self.source_course.id)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
