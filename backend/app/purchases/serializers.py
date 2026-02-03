from rest_framework import serializers
from .models import Purchase
from courses.serializers import CourseBriefSerializer


class PurchaseSerializer(serializers.ModelSerializer):
    course = CourseBriefSerializer(read_only=True)

    class Meta:
        model = Purchase
        fields = ("id", "payment_id", "course", "amount", "status", "transaction_id", "created_at")
        read_only_fields = ("id", "payment_id", "amount", "status", "transaction_id", "created_at")


class PurchaseCreateSerializer(serializers.Serializer):
    course_id = serializers.CharField()

    def validate_course_id(self, value):
        from courses.models import Course

        try:
            course = Course.objects.get(id=value)
        except Course.DoesNotExist:
            raise serializers.ValidationError("Course not found")
        if not course.is_free:
            if not course.price or course.price <= 0:
                raise serializers.ValidationError("Course price is not set")
            if course.discount_price is not None:
                if course.discount_price <= 0:
                    raise serializers.ValidationError("Course discount price is invalid")
                if course.discount_price >= course.price:
                    raise serializers.ValidationError("Course discount price must be lower than price")
        self.context["course"] = course
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        course = self.context["course"]
        from .models import Purchase

        amount = int(course.effective_price)
        defaults = {
            "status": "paid" if course.is_free else "pending",
            "amount": amount,
        }
        purchase, created = Purchase.objects.get_or_create(user=user, course=course, defaults=defaults)
        self.context["purchase_created"] = created
        if not created:
            updates = []
            if purchase.amount != amount and amount:
                purchase.amount = amount
                updates.append("amount")
            if course.is_free and purchase.status != "paid":
                purchase.status = "paid"
                updates.append("status")
            if updates:
                purchase.save(update_fields=updates)
        return purchase
