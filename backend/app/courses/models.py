from django.db import models
from django.utils.text import slugify


class Course(models.Model):
    LEVEL_CHOICES = (
        ("Начинающий", "Начинающий"),
        ("Средний", "Средний"),
        ("Продвинутый", "Продвинутый"),
    )

    id = models.SlugField(primary_key=True, max_length=100, allow_unicode=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    full_description = models.TextField(blank=True)
    is_free = models.BooleanField(default=False)
    level = models.CharField(max_length=32, choices=LEVEL_CHOICES, default="Начинающий")
    price = models.IntegerField(blank=True, null=True)
    preview_image = models.ImageField(upload_to="courses/previews/", blank=True, null=True)
    background_video_url = models.URLField(blank=True, null=True)
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=255, blank=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Автоматически генерируем slug (поддерживаем кириллицу), если не задан
        if not self.id and self.title:
            self.id = slugify(self.title, allow_unicode=True)
        super().save(*args, **kwargs)


class Module(models.Model):
    course = models.ForeignKey(Course, related_name="modules", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.course_id} - {self.title}"


class Lesson(models.Model):
    module = models.ForeignKey(Module, related_name="lessons", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    video_url = models.URLField()
    order = models.PositiveIntegerField(default=1)
    duration = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title
