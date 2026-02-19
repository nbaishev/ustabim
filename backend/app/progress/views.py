from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsModeratorOrAdmin
from users.models import User
from .models import UserLessonProgress
from .serializers import UserLessonProgressSerializer
from courses.models import Course, Lesson
from courses.utils import user_has_course_access


class ProgressListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            UserLessonProgress.objects.filter(user=request.user)
            .select_related("lesson", "lesson__module", "lesson__module__course")
        )
        serializer = UserLessonProgressSerializer(qs, many=True)
        return Response(serializer.data)


class ProgressCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        course_id = request.data.get("course_id")
        lesson_id = request.data.get("lesson_id")
        if not course_id or not lesson_id:
            return Response({"detail": "course_id and lesson_id are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({"detail": "Course not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            lesson = Lesson.objects.get(id=lesson_id, module__course=course)
        except Lesson.DoesNotExist:
            return Response({"detail": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user_has_course_access(request.user, course):
            return Response({"detail": "Access denied"}, status=status.HTTP_403_FORBIDDEN)

        progress, _ = UserLessonProgress.objects.get_or_create(
            user=request.user,
            lesson=lesson,
            defaults={
                "is_completed": True,
                "completed_at": timezone.now(),
                "last_viewed_at": timezone.now(),
            },
        )
        if not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = timezone.now()
        progress.last_viewed_at = timezone.now()
        progress.save(update_fields=["is_completed", "completed_at", "last_viewed_at"])

        serializer = UserLessonProgressSerializer(progress)
        return Response(serializer.data)


class ProgressViewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        course_id = request.data.get("course_id")
        lesson_id = request.data.get("lesson_id")
        if not course_id or not lesson_id:
            return Response({"detail": "course_id and lesson_id are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({"detail": "Course not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            lesson = Lesson.objects.get(id=lesson_id, module__course=course)
        except Lesson.DoesNotExist:
            return Response({"detail": "Lesson not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user_has_course_access(request.user, course):
            return Response({"detail": "Access denied"}, status=status.HTTP_403_FORBIDDEN)

        progress, _ = UserLessonProgress.objects.get_or_create(
            user=request.user,
            lesson=lesson,
            defaults={"last_viewed_at": timezone.now()},
        )
        progress.last_viewed_at = timezone.now()
        progress.save(update_fields=["last_viewed_at"])

        progress.refresh_from_db()
        serializer = UserLessonProgressSerializer(progress)
        return Response(serializer.data)


class ModeratorCourseCompletionView(APIView):
    permission_classes = [IsModeratorOrAdmin]

    def get(self, request):
        course_id = request.query_params.get("course_id")
        completed_only = request.query_params.get("completed_only", "false").lower() in ("1", "true", "yes")
        if not course_id:
            return Response({"detail": "course_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            course = Course.objects.annotate(
                total_lessons=Count("modules__lessons", distinct=True),
            ).get(id=course_id)
        except Course.DoesNotExist:
            return Response({"detail": "Course not found"}, status=status.HTTP_404_NOT_FOUND)

        total_lessons = int(getattr(course, "total_lessons", 0) or 0)
        users_qs = (
            User.objects.filter(
                Q(lesson_progress__lesson__module__course=course)
                | Q(purchases__course=course, purchases__status="paid")
            )
            .distinct()
            .annotate(
                completed_lessons=Count(
                    "lesson_progress__lesson",
                    filter=Q(
                        lesson_progress__lesson__module__course=course,
                        lesson_progress__is_completed=True,
                    ),
                    distinct=True,
                ),
                last_completed_at=Max(
                    "lesson_progress__completed_at",
                    filter=Q(
                        lesson_progress__lesson__module__course=course,
                        lesson_progress__is_completed=True,
                    ),
                ),
            )
            .order_by("-completed_lessons", "email")
        )

        users = list(users_qs)
        completed_users = 0
        results = []
        for course_user in users:
            completed_lessons = int(getattr(course_user, "completed_lessons", 0) or 0)
            progress_percent = (completed_lessons / total_lessons) * 100 if total_lessons > 0 else 0
            is_completed = total_lessons > 0 and completed_lessons >= total_lessons
            if is_completed:
                completed_users += 1
            if completed_only and not is_completed:
                continue
            results.append(
                {
                    "user_id": str(course_user.id),
                    "name": course_user.name,
                    "email": course_user.email,
                    "completed_lessons": completed_lessons,
                    "total_lessons": total_lessons,
                    "progress_percent": round(min(progress_percent, 100), 2),
                    "is_completed": is_completed,
                    "last_completed_at": course_user.last_completed_at,
                }
            )

        return Response(
            {
                "course": {
                    "id": course.id,
                    "title": course.title,
                    "total_lessons": total_lessons,
                },
                "completed_only": completed_only,
                "total_users": len(users),
                "completed_users": completed_users,
                "results": results,
            }
        )
