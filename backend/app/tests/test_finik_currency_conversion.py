from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from courses.models import Course
from purchases.finik import convert_usd_to_kgs_amount
from users.models import User


def auth_headers(user):
    token = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class FinikCurrencyConversionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="pay@example.com", password="pass", name="Pay User")
        self.course = Course.objects.create(
            id="usd-course",
            title="USD Course",
            description="Paid",
            full_description="Paid",
            is_free=False,
            price=100,
            level="Средний",
        )

    def test_helper_rounds_half_up_to_whole_som(self):
        self.assertEqual(convert_usd_to_kgs_amount(57), 4988)

    def test_purchase_response_keeps_usd_but_finik_receives_kgs(self):
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

        with (
            override_settings(FINIK_REDIRECT_URL="https://academy.local/payment/success"),
            patch("purchases.views.get_config", return_value=finik_config),
            patch("purchases.views.create_payment", return_value=fake_response) as create_payment_mock,
        ):
            response = self.client.post(
                reverse("purchase-list"),
                {"course_id": self.course.id},
                format="json",
                **auth_headers(self.user),
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], 100)
        self.assertEqual(create_payment_mock.call_args.kwargs["amount"], 8750)
        self.assertEqual(response.data["payment_url"], "https://pay.test.local/checkout?payment-methods=CARD")

    def test_purchase_response_appends_card_payment_method_to_existing_query(self):
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
        fake_response.json.return_value = {"paymentUrl": "https://pay.test.local/checkout?lang=ru"}
        fake_response.text = ""

        with (
            override_settings(FINIK_REDIRECT_URL="https://academy.local/payment/success"),
            patch("purchases.views.get_config", return_value=finik_config),
            patch("purchases.views.create_payment", return_value=fake_response),
        ):
            response = self.client.post(
                reverse("purchase-list"),
                {"course_id": self.course.id},
                format="json",
                **auth_headers(self.user),
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["payment_url"],
            "https://pay.test.local/checkout?lang=ru&payment-methods=CARD",
        )
