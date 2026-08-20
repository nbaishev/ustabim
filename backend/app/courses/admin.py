from django.contrib import admin
from .models import Course, Module, Lesson


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "level",
        "delivery_mode",
        "mentor_telegram_username",
        "is_free",
        "published",
        "price",
        "discount_price",
        "is_featured",
        "sort_order",
    )
    list_editable = ("sort_order",)
    search_fields = ("title", "description", "full_description")
    list_filter = ("level", "delivery_mode", "is_free", "published", "is_featured")
    prepopulated_fields = {"id": ("title",)}
    inlines = [ModuleInline]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order")
    list_filter = ("course",)
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "order")
    list_filter = ("module",)
