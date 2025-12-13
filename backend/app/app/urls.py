from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from courses.views import CourseViewSet, AdminCourseViewSet, StatsView
from purchases.views import PurchaseViewSet
from users.views import GoogleLoginView, LogoutView, MeView, MyCoursesView
from progress.views import ProgressListView, ProgressCompleteView
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="course")
router.register(r"purchase", PurchaseViewSet, basename="purchase")
router.register(r"admin/courses", AdminCourseViewSet, basename="admin-course")

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
    path("api/admin/stats/", StatsView.as_view(), name="admin-stats"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

