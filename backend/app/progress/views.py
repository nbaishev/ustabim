from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
            defaults={"is_completed": True, "completed_at": timezone.now()},
        )
        if not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = timezone.now()
            progress.save(update_fields=["is_completed", "completed_at"])

        serializer = UserLessonProgressSerializer(progress)
        return Response(serializer.data)

