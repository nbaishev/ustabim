from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0005_merge_0004_and_0002_lesson_additional_materials"),
        ("purchases", "0002_add_payment_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserCourseDiscount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_email", models.EmailField(max_length=254)),
                ("percent_off", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("amount_off", models.PositiveIntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_discounts",
                        to="courses.course",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("user_email", "course")},
            },
        ),
    ]
