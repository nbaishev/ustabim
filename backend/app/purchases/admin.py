from django.contrib import admin
from .models import Purchase


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "course", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__email", "course__title", "transaction_id")
