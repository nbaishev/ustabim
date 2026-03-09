from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import IsAdminUser
from rest_framework.routers import DefaultRouter
from courses.views import CourseViewSet, AdminCourseViewSet, StatsView
from purchases.views import PurchaseViewSet, FinikWebhookView
from users.views import GoogleLoginView, LogoutView, MeView, MyCoursesView
from progress.views import ProgressListView, ProgressCompleteView, ProgressViewView, ModeratorCourseCompletionView
from entrance_tests.views import (
    EntranceQuizUnifiedView,
    FreeCourseBenefitStatusView,
    FreeCourseBenefitClaimView,
)
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="course")
router.register(r"purchase", PurchaseViewSet, basename="purchase")
router.register(r"moderator/courses", AdminCourseViewSet, basename="moderator-course")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/auth/login/google/", GoogleLoginView.as_view(), name="auth-google"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/me/", MeView.as_view(), name="me"),
    path("api/me/courses/", MyCoursesView.as_view(), name="me-courses"),
    path("api/me/progress/", ProgressListView.as_view(), name="me-progress"),
    path("api/me/progress/complete/", ProgressCompleteView.as_view(), name="me-progress-complete"),
    path("api/me/progress/view/", ProgressViewView.as_view(), name="me-progress-view"),
    path("api/entrance-test/", EntranceQuizUnifiedView.as_view(), name="entrance-test-unified"),
    path(
        "api/free-course-benefits/courses/<str:course_id>/status/",
        FreeCourseBenefitStatusView.as_view(),
        name="free-course-benefit-status",
    ),
    path(
        "api/free-course-benefits/courses/<str:course_id>/claim/",
        FreeCourseBenefitClaimView.as_view(),
        name="free-course-benefit-claim",
    ),
    path(
        "api/moderator/course-completions/",
        ModeratorCourseCompletionView.as_view(),
        name="moderator-course-completions",
    ),
    path("api/moderator/stats/", StatsView.as_view(), name="moderator-stats"),
    path("api/payments/finik/webhook/", FinikWebhookView.as_view(), name="finik-webhook"),
]

if settings.DEBUG:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]
else:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(permission_classes=[IsAdminUser]), name="schema"),
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[IsAdminUser]),
            name="swagger-ui",
        ),
        path(
            "api/redoc/",
            SpectacularRedocView.as_view(url_name="schema", permission_classes=[IsAdminUser]),
            name="redoc",
        ),
    ]
