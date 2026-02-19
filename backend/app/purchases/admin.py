from django.contrib import admin
from .models import Purchase, UserCourseDiscount


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "course", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__email", "course__title", "transaction_id")


@admin.register(UserCourseDiscount)
class UserCourseDiscountAdmin(admin.ModelAdmin):
    list_display = ("user_email", "course", "percent_off", "amount_off", "is_active", "expires_at")
    list_filter = ("is_active", "course")
    search_fields = ("user_email", "course__title")
