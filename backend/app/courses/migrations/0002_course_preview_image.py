from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="preview_image",
            field=models.ImageField(blank=True, null=True, upload_to="courses/previews/"),
        ),
    ]
