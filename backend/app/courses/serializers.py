from rest_framework import serializers
from .models import Course, Module, Lesson


class LessonPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ("id", "title", "order", "duration")


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ("id", "title", "order", "duration", "video_url")


class ModulePublicSerializer(serializers.ModelSerializer):
    lessons = LessonPublicSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ("id", "title", "order", "lessons")


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ("id", "title", "order", "lessons")


class CourseBriefSerializer(serializers.ModelSerializer):
    lessons_count = serializers.SerializerMethodField()
    modules_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = (
            "id",
            "title",
            "description",
            "is_free",
            "level",
            "price",
            "preview_image",
            "is_featured",
            "lessons_count",
            "modules_count",
        )

    def get_lessons_count(self, obj):
        return getattr(obj, "lessons_count", 0)

    def get_modules_count(self, obj):
        return getattr(obj, "modules_count", 0)


class CourseSerializer(serializers.ModelSerializer):
    lessons_count = serializers.SerializerMethodField()
    modules_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = (
            "id",
            "title",
            "description",
            "full_description",
            "is_free",
            "level",
            "price",
            "preview_image",
            "background_video_url",
            "seo_title",
            "seo_description",
            "is_featured",
            "created_at",
            "updated_at",
            "lessons_count",
            "modules_count",
        )

    def get_lessons_count(self, obj):
        return getattr(obj, "lessons_count", 0)

    def get_modules_count(self, obj):
        return getattr(obj, "modules_count", 0)


class CourseDetailSerializer(CourseSerializer):
    modules = ModulePublicSerializer(many=True, read_only=True)

    class Meta(CourseSerializer.Meta):
        fields = CourseSerializer.Meta.fields + ("modules",)


class CourseContentSerializer(CourseSerializer):
    modules = ModuleSerializer(many=True, read_only=True)

    class Meta(CourseSerializer.Meta):
        fields = CourseSerializer.Meta.fields + ("modules",)


class CourseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = (
            "id",
            "title",
            "description",
            "full_description",
            "is_free",
            "level",
            "price",
            "preview_image",
            "background_video_url",
            "seo_title",
            "seo_description",
            "is_featured",
        )
