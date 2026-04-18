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
    Purchase = apps.get_model("purchases", "Purchase")
    UserCourseDiscount = apps.get_model("purchases", "UserCourseDiscount")

    for purchase in Purchase.objects.all().iterator():
        converted_amount = _convert_from_kgs_to_usd(purchase.amount)
        if purchase.amount != converted_amount:
            purchase.amount = converted_amount
            purchase.save(update_fields=["amount"])

    for discount in UserCourseDiscount.objects.exclude(amount_off__isnull=True).iterator():
        converted_amount_off = _convert_from_kgs_to_usd(discount.amount_off)
        if discount.amount_off != converted_amount_off:
            discount.amount_off = converted_amount_off
            discount.save(update_fields=["amount_off"])


def backwards(apps, schema_editor):
    Purchase = apps.get_model("purchases", "Purchase")
    UserCourseDiscount = apps.get_model("purchases", "UserCourseDiscount")

    for purchase in Purchase.objects.all().iterator():
        converted_amount = _convert_from_usd_to_kgs(purchase.amount)
        if purchase.amount != converted_amount:
            purchase.amount = converted_amount
            purchase.save(update_fields=["amount"])

    for discount in UserCourseDiscount.objects.exclude(amount_off__isnull=True).iterator():
        converted_amount_off = _convert_from_usd_to_kgs(discount.amount_off)
        if discount.amount_off != converted_amount_off:
            discount.amount_off = converted_amount_off
            discount.save(update_fields=["amount_off"])


class Migration(migrations.Migration):
    dependencies = [
        ("purchases", "0003_usercoursediscount"),
        ("courses", "0008_convert_course_prices_to_usd"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
