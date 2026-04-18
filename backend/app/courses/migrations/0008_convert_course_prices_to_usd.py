from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations


USD_TO_KGS_RATE = Decimal("87.5")


def _convert_from_kgs_to_usd(value):
    if value is None or value <= 0:
        return value
    converted = Decimal(value) / USD_TO_KGS_RATE
    return int(converted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _convert_from_usd_to_kgs(value):
    if value is None or value <= 0:
        return value
    converted = Decimal(value) * USD_TO_KGS_RATE
    return int(converted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def forwards(apps, schema_editor):
    Course = apps.get_model("courses", "Course")

    for course in Course.objects.all().iterator():
        updates = []
        converted_price = _convert_from_kgs_to_usd(course.price)
        converted_discount_price = _convert_from_kgs_to_usd(course.discount_price)
        if course.price != converted_price:
            course.price = converted_price
            updates.append("price")
        if course.discount_price != converted_discount_price:
            course.discount_price = converted_discount_price
            updates.append("discount_price")
        if updates:
            course.save(update_fields=updates)


def backwards(apps, schema_editor):
    Course = apps.get_model("courses", "Course")

    for course in Course.objects.all().iterator():
        updates = []
        converted_price = _convert_from_usd_to_kgs(course.price)
        converted_discount_price = _convert_from_usd_to_kgs(course.discount_price)
        if course.price != converted_price:
            course.price = converted_price
            updates.append("price")
        if course.discount_price != converted_discount_price:
            course.discount_price = converted_discount_price
            updates.append("discount_price")
        if updates:
            course.save(update_fields=updates)


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0007_alter_lesson_additional_materials_text"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
