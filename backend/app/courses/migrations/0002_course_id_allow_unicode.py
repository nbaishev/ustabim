from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="id",
            field=models.SlugField(
                allow_unicode=True,
                max_length=100,
                primary_key=True,
                serialize=False,
            ),
        ),
    ]
