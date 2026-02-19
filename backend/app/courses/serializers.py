from django.apps import apps
from django.utils import timezone
from rest_framework import serializers
from .models import Course, Module, Lesson


class LessonPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ("id", "title", "order", "duration")


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ("id", "title", "order", "duration", "video_url", "additional_materials")


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


class CoursePriceMixin:
    def get_current_price(self, obj):
        base_price = int(obj.effective_price)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False) or obj.is_free:
            return base_price

        UserCourseDiscount = apps.get_model("purchases", "UserCourseDiscount")
        discount = (
            UserCourseDiscount.objects
            .filter(user_email__iexact=user.email, course=obj, is_active=True)
            .filter(expires_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if discount is None:
            discount = (
                UserCourseDiscount.objects
                .filter(user_email__iexact=user.email, course=obj, is_active=True, expires_at__gt=timezone.now())
                .order_by("-created_at")
                .first()
            )

        if discount is None:
            return base_price

        if discount.percent_off is not None:
            amount = base_price - int(base_price * discount.percent_off / 100)
        else:
            amount = base_price - int(discount.amount_off or 0)
        return max(amount, 0)


class CourseBriefSerializer(CoursePriceMixin, serializers.ModelSerializer):
    current_price = serializers.SerializerMethodField()
    lessons_count = serializers.SerializerMethodField()
    modules_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = (
            "id",
            "title",
            "description",
            "is_free",
            "published",
            "level",
            "price",
            "discount_price",
            "current_price",
            "preview_image",
            "is_featured",
            "lessons_count",
            "modules_count",
        )

    def get_lessons_count(self, obj):
        return getattr(obj, "lessons_count", 0)

    def get_modules_count(self, obj):
        return getattr(obj, "modules_count", 0)


class CourseSerializer(CoursePriceMixin, serializers.ModelSerializer):
    current_price = serializers.SerializerMethodField()
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
            "published",
            "level",
            "price",
            "discount_price",
            "current_price",
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
            "published",
            "level",
            "price",
            "discount_price",
            "preview_image",
            "background_video_url",
            "seo_title",
            "seo_description",
            "is_featured",
        )
        extra_kwargs = {
            # Позволяем не указывать slug при создании — он сгенерируется из title
            "id": {"required": False},
        }

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        is_free = attrs.get("is_free", getattr(instance, "is_free", False))
        price = attrs.get("price", getattr(instance, "price", None))
        discount_price = attrs.get("discount_price", getattr(instance, "discount_price", None))

        if not is_free:
            if not price or price <= 0:
                raise serializers.ValidationError("Course price is not set")
        if discount_price is not None:
            if not price or price <= 0:
                raise serializers.ValidationError("Course price is required to set discount")
            if discount_price <= 0:
                raise serializers.ValidationError("Discount price must be greater than 0")
            if discount_price >= price:
                raise serializers.ValidationError("Discount price must be lower than regular price")
        return attrs
