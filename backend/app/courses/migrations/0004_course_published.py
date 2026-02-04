from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0003_course_discount_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="published",
            field=models.BooleanField(default=True),
        ),
    ]
