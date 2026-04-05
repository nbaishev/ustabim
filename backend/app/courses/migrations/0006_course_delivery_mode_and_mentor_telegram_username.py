from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0005_merge_0004_and_0002_lesson_additional_materials"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="delivery_mode",
            field=models.CharField(
                choices=[("online", "Онлайн"), ("offline", "Оффлайн")],
                default="online",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="mentor_telegram_username",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
