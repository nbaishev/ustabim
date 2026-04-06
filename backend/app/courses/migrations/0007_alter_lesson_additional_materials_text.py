from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0006_course_delivery_mode_and_mentor_telegram_username"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lesson",
            name="additional_materials",
            field=models.TextField(blank=True, null=True),
        ),
    ]
