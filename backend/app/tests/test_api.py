from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User
from courses.models import Course, Module, Lesson
from purchases.models import Purchase, UserCourseDiscount


def auth_headers(user):
    token = RefreshToken.for_user(user).access_token
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class AuthTests(APITestCase):
    def test_google_login_requires_token(self):
        url = reverse("auth-google")
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CourseAccessTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="user@example.com", password="pass", name="User")
        self.free_course = Course.objects.create(
            id="free-course",
            title="Free Course",
            description="Free",
            full_description="Free",
            is_free=True,
            level="Начинающий",
        )
        free_module = Module.objects.create(course=self.free_course, title="Mod1", order=1)
        Lesson.objects.create(module=free_module, title="Lesson1", video_url="https://example.com", order=1)

        self.paid_course = Course.objects.create(
            id="paid-course",
            title="Paid Course",
            description="Paid",
            full_description="Paid",
            is_free=False,
            price=1000,
            level="Средний",
        )
        paid_module = Module.objects.create(course=self.paid_course, title="Mod1", order=1)
        Lesson.objects.create(module=paid_module, title="Lesson1", video_url="https://example.com", order=1)

    def test_free_course_content_accessible(self):
        url = reverse("course-content", kwargs={"id": self.free_course.id})
        response = self.client.get(url, **auth_headers(self.user))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.free_course.id)

    def test_paid_course_denied_without_purchase(self):
        url = reverse("course-content", kwargs={"id": self.paid_course.id})
        response = self.client.get(url, **auth_headers(self.user))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


    def test_course_detail_returns_current_price_with_individual_discount(self):
        UserCourseDiscount.objects.create(
            user_email=self.user.email,
            course=self.paid_course,
            percent_off=20,
        )
        url = reverse("course-detail", kwargs={"id": self.paid_course.id})
        response = self.client.get(url, **auth_headers(self.user))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["price"], 1000)
        self.assertEqual(response.data["current_price"], 800)

    def test_paid_course_allowed_after_purchase(self):
        Purchase.objects.create(user=self.user, course=self.paid_course, status="paid")
        url = reverse("course-content", kwargs={"id": self.paid_course.id})
        response = self.client.get(url, **auth_headers(self.user))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AdminCourseTests(APITestCase):
    def setUp(self):
        self.moderator = User.objects.create_user(
            email="mod@example.com", password="pass", name="Mod", role="moderator"
        )
        self.user = User.objects.create_user(email="user2@example.com", password="pass", name="User")

    def test_moderator_can_create_course(self):
        url = reverse("admin-course-list")
        data = {
            "id": "new-course",
            "title": "New Course",
            "description": "Desc",
            "full_description": "Full",
            "is_free": True,
            "level": "Начинающий",
        }
        response = self.client.post(url, data, **auth_headers(self.moderator))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_regular_user_cannot_create_course(self):
        url = reverse("admin-course-list")
        data = {
            "id": "fail-course",
            "title": "New Course",
            "description": "Desc",
            "full_description": "Full",
            "is_free": True,
            "level": "Начинающий",
        }
        response = self.client.post(url, data, **auth_headers(self.user))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)



class IndividualDiscountTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="winner@example.com", password="pass", name="Winner")
        self.course = Course.objects.create(
            id="discount-course",
            title="Discount Course",
            description="Paid",
            full_description="Paid",
            is_free=False,
            price=1000,
            level="Средний",
        )

    def test_full_individual_discount_marks_purchase_paid(self):
        UserCourseDiscount.objects.create(
            user_email="winner@example.com",
            course=self.course,
            percent_off=100,
        )
        url = reverse("purchase-list")
        response = self.client.post(url, {"course_id": self.course.id}, format="json", **auth_headers(self.user))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], 0)
        self.assertEqual(response.data["status"], "paid")

