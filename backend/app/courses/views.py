from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsModeratorOrAdmin
from .models import Course, Module, Lesson
from .serializers import (
    CourseBriefSerializer,
    CourseContentSerializer,
    CourseDetailSerializer,
    CourseSerializer,
    CourseWriteSerializer,
    LessonSerializer,
    LessonPublicSerializer,
    ModulePublicSerializer,
)
from .utils import user_has_course_access
from purchases.models import Purchase
from users.models import User


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = "id"
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [AllowAny]
    search_fields = ["title", "description", "full_description"]
    filterset_fields = ["level", "is_free", "is_featured"]
    ordering_fields = ["created_at", "title"]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "action", None) == "retrieve":
            qs = qs.prefetch_related("modules__lessons")
        qs = qs.annotate(
            lessons_count=Count("modules__lessons", distinct=True),
            modules_count=Count("modules", distinct=True),
        )
        price_filter = self.request.query_params.get("price")
        if price_filter == "free":
            qs = qs.filter(is_free=True)
        elif price_filter == "paid":
            qs = qs.filter(is_free=False)
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CourseDetailSerializer
        return CourseSerializer

    @action(detail=True, methods=["get"], url_path="modules")
    def modules(self, request, id=None):
        course = self.get_object()
        serializer = ModulePublicSerializer(course.modules.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="lessons")
    def lessons(self, request, id=None):
        course = self.get_object()
        lessons_qs = Lesson.objects.filter(module__course=course)
        serializer = LessonPublicSerializer(lessons_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="content", permission_classes=[AllowAny])
    def content(self, request, id=None):
        course = get_object_or_404(
            Course.objects.annotate(
                lessons_count=Count("modules__lessons", distinct=True),
                modules_count=Count("modules", distinct=True),
            ).prefetch_related("modules__lessons"),
            id=id,
        )
        if not course.is_free:
            if not request.user or not request.user.is_authenticated:
                return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
            if not user_has_course_access(request.user, course):
                return Response({"detail": "Access denied"}, status=status.HTTP_403_FORBIDDEN)
        serializer = CourseContentSerializer(course, context={"request": request})
        return Response(serializer.data)


class AdminCourseViewSet(viewsets.ModelViewSet):
    lookup_field = "id"
    queryset = Course.objects.all()
    permission_classes = [IsModeratorOrAdmin]
    serializer_class = CourseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, "action", None) == "retrieve":
            qs = qs.prefetch_related("modules__lessons")
        return qs.annotate(
            lessons_count=Count("modules__lessons", distinct=True),
            modules_count=Count("modules", distinct=True),
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CourseContentSerializer
        if self.action in ("create", "update", "partial_update"):
            return CourseWriteSerializer
        return CourseSerializer

    @action(detail=True, methods=["post"], url_path="modules")
    def create_module(self, request, id=None):
        course = self.get_object()
        title = request.data.get("title")
        order = request.data.get("order") or 1
        if not title:
            return Response({"detail": "title is required"}, status=status.HTTP_400_BAD_REQUEST)
        module = Module.objects.create(course=course, title=title, order=order)
        return Response(ModulePublicSerializer(module).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="lessons")
    def create_lesson(self, request, id=None):
        course = self.get_object()
        module_id = request.data.get("module_id")
        title = request.data.get("title")
        video_url = request.data.get("video_url")
        additional_materials = request.data.get("additional_materials")
        order = request.data.get("order") or 1
        duration = request.data.get("duration", "")
        if not all([module_id, title, video_url]):
            return Response({"detail": "module_id, title and video_url are required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            module = Module.objects.get(id=module_id, course=course)
        except Module.DoesNotExist:
            return Response({"detail": "Module not found"}, status=status.HTTP_404_NOT_FOUND)
        lesson = Lesson.objects.create(
            module=module,
            title=title,
            video_url=video_url,
            additional_materials=additional_materials,
            order=order,
            duration=duration,
        )
        return Response(LessonSerializer(lesson).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"lessons/(?P<lesson_id>[^/.]+)")
    def update_lesson(self, request, id=None, lesson_id=None):
        course = self.get_object()
        if lesson_id is None:
            return Response({"detail": "lesson_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            lesson = Lesson.objects.get(id=lesson_id, module__course=course)
        except Lesson.DoesNotExist:
            return Response({"detail": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)

        if "additional_materials" not in request.data:
            return Response({"detail": "additional_materials is required"}, status=status.HTTP_400_BAD_REQUEST)

        lesson.additional_materials = request.data.get("additional_materials")
        lesson.save(update_fields=["additional_materials"])
        return Response(LessonSerializer(lesson).data)


class StatsView(APIView):
    permission_classes = [IsModeratorOrAdmin]

    def get(self, request):
        total_users = User.objects.count()
        total_courses = Course.objects.count()
        total_purchases = Purchase.objects.count()

        popular = (
            Course.objects.annotate(enrollments=Count("purchases", filter=Q(purchases__status="paid")))
            .order_by("-enrollments")[:5]
        )
        popular_data = [
            {"id": course.id, "title": course.title, "enrollments": course.enrollments}
            for course in popular
        ]
        return Response(
            {
                "total_users": total_users,
                "total_courses": total_courses,
                "total_purchases": total_purchases,
                "most_popular_courses": popular_data,
            }
        )


class PublicStatsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "total_users": User.objects.count(),
            }
        )
