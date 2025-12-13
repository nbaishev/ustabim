from rest_framework import serializers
from .models import Purchase
from courses.serializers import CourseBriefSerializer


class PurchaseSerializer(serializers.ModelSerializer):
    course = CourseBriefSerializer(read_only=True)

    class Meta:
        model = Purchase
        fields = ("id", "course", "status", "transaction_id", "created_at")
        read_only_fields = ("id", "status", "transaction_id", "created_at")


class PurchaseCreateSerializer(serializers.Serializer):
    course_id = serializers.CharField()

    def validate_course_id(self, value):
        from courses.models import Course

        try:
            course = Course.objects.get(id=value)
        except Course.DoesNotExist:
            raise serializers.ValidationError("Course not found")
        self.context["course"] = course
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        course = self.context["course"]
        from .models import Purchase

        purchase, created = Purchase.objects.get_or_create(
            user=user,
            course=course,
            defaults={
                # Заглушка: сразу оплачено, чтобы пользователь получил доступ.
                "status": "paid" if not course.is_free else "paid",
                "transaction_id": "mock-txn",
            },
        )
        return purchase
