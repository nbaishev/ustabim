from rest_framework import serializers
from .models import UserLessonProgress
from courses.serializers import LessonSerializer


class UserLessonProgressSerializer(serializers.ModelSerializer):
    lesson = LessonSerializer(read_only=True)
    course_id = serializers.SerializerMethodField()

    class Meta:
        model = UserLessonProgress
        fields = ("id", "lesson", "course_id", "is_completed", "completed_at")
        read_only_fields = ("id", "completed_at")

    def get_course_id(self, obj):
        return obj.lesson.module.course_id
