from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, GoogleOAuthConfig


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("name", "avatar", "google_id")}),
        ("Permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "name", "password1", "password2", "role"),
        }),
    )
    list_display = ("email", "name", "role", "is_staff")
    search_fields = ("email", "name")
    ordering = ("email",)


@admin.register(GoogleOAuthConfig)
class GoogleOAuthConfigAdmin(admin.ModelAdmin):
    list_display = ("client_id", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("client_id",)
