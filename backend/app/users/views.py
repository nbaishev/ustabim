from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from django.db import models
import requests
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from allauth.socialaccount.models import SocialAccount, SocialApp

from .models import User, GoogleOAuthConfig
from .serializers import UserSerializer


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        token = request.data.get("id_token")
        auth_code = request.data.get("code")
        redirect_uri = request.data.get("redirect_uri")
        code_verifier = request.data.get("code_verifier")
        id_info = None

        if not token and not auth_code:
            return Response({"detail": "id_token or code is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve client settings: priority SocialApp (allauth) -> DB config -> env
        social_app = SocialApp.objects.filter(provider="google").first()
        db_config = GoogleOAuthConfig.objects.filter(is_active=True).order_by("-updated_at").first()

        client_id = (
            social_app.client_id
            if social_app
            else db_config.client_id if db_config else settings.GOOGLE_CLIENT_ID
        )
        client_secret = (
            social_app.secret
            if social_app
            else db_config.client_secret if db_config else settings.GOOGLE_CLIENT_SECRET
        )
        default_redirect_uri = db_config.redirect_uri if db_config and db_config.redirect_uri else None

        if not client_id:
            return Response({"detail": "Google OAuth client_id не сконфигурирован"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # If we received an auth code, exchange it for id_token
        if auth_code:
            if not client_id or not client_secret:
                return Response({"detail": "Google OAuth client_id/client_secret not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": auth_code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri or default_redirect_uri or "",
            }
            if code_verifier:
                data["code_verifier"] = code_verifier
            resp = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=10)
            if resp.status_code != 200:
                return Response({"detail": "Failed to exchange code", "error": resp.text}, status=status.HTTP_400_BAD_REQUEST)
            token_payload = resp.json()
            token = token_payload.get("id_token")
            if not token:
                return Response({"detail": "No id_token returned from Google"}, status=status.HTTP_400_BAD_REQUEST)

        dev_bypass = settings.DEBUG and settings.GOOGLE_DEV_BYPASS_TOKEN and token == settings.GOOGLE_DEV_BYPASS_TOKEN
        if dev_bypass:
            email = request.data.get("email") or "devuser@example.com"
            name = request.data.get("name") or email.split("@")[0]
            avatar = request.data.get("avatar")
            google_sub = "dev"
        else:
            try:
                id_info = id_token.verify_oauth2_token(
                    token,
                    google_requests.Request(),
                    client_id,
                )
            except Exception:
                return Response({"detail": "Invalid Google token"}, status=status.HTTP_400_BAD_REQUEST)

            email = id_info.get("email")
            google_sub = id_info.get("sub")
            name = id_info.get("name") or (email.split("@")[0] if email else "User")
            avatar = id_info.get("picture")

            if not email:
                return Response({"detail": "Google token missing email"}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "name": name,
                "google_id": google_sub,
                "avatar": avatar,
            },
        )

        if not created and not user.google_id:
            user.google_id = google_sub
            user.save(update_fields=["google_id"])

        # Ensure allauth social account linkage
        social_account, _ = SocialAccount.objects.get_or_create(
            user=user,
            provider="google",
            uid=google_sub,
            defaults={"extra_data": id_info if not dev_bypass else {}},
        )
        if not social_account.extra_data and not dev_bypass and id_info:
            social_account.extra_data = id_info
            social_account.save(update_fields=["extra_data"])

        refresh = RefreshToken.for_user(user)
        data = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        }
        return Response(data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # With SimpleJWT we can rely on client side token discard; blacklist can be added later.
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class MyCoursesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from courses.models import Course
        from courses.serializers import CourseBriefSerializer
        from purchases.models import Purchase

        purchased_ids = Purchase.objects.filter(
            user=request.user, status="paid"
        ).values_list("course_id", flat=True)

        courses_qs = Course.objects.filter(
            models.Q(is_free=True) | models.Q(id__in=purchased_ids)
        )
        serializer = CourseBriefSerializer(courses_qs, many=True)
        return Response(serializer.data)
