from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0002_course_id_allow_unicode"),
        ("courses", "0002_course_preview_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="discount_price",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
