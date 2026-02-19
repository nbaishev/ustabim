from django.utils import timezone
from rest_framework import serializers

from courses.serializers import CourseBriefSerializer

from .models import Purchase, UserCourseDiscount


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

    @staticmethod
    def _get_individual_discounted_amount(user_email: str, course, base_amount: int) -> int:
        discount = (
            UserCourseDiscount.objects
            .filter(user_email__iexact=user_email, course=course, is_active=True)
            .filter(expires_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if discount is None:
            discount = (
                UserCourseDiscount.objects
                .filter(user_email__iexact=user_email, course=course, is_active=True, expires_at__gt=timezone.now())
                .order_by("-created_at")
                .first()
            )

        if discount is None:
            return base_amount

        if discount.percent_off is not None:
            amount = base_amount - int(base_amount * discount.percent_off / 100)
        else:
            amount = base_amount - int(discount.amount_off or 0)

        return max(amount, 0)

    def create(self, validated_data):
        user = self.context["request"].user
        course = self.context["course"]

        amount = int(course.effective_price)
        if not course.is_free:
            amount = self._get_individual_discounted_amount(user.email, course, amount)

        defaults = {
            "status": "paid" if course.is_free or amount == 0 else "pending",
            "amount": amount,
        }
        purchase, created = Purchase.objects.get_or_create(user=user, course=course, defaults=defaults)
        self.context["purchase_created"] = created
        if not created:
            updates = []
            if purchase.amount != amount:
                purchase.amount = amount
                updates.append("amount")
            expected_status = "paid" if course.is_free or amount == 0 else purchase.status
            if expected_status == "paid" and purchase.status != "paid":
                purchase.status = "paid"
                updates.append("status")
            if updates:
                purchase.save(update_fields=updates)
        return purchase
