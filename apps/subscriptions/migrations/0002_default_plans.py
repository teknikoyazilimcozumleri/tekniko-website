from django.db import migrations


def create_default_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    plans = [
        {"name": "Basic", "slug": "basic", "description": "Temel özellikler", "price": 99, "currency": "TRY", "sort_order": 1},
        {"name": "Pro", "slug": "pro", "description": "Gelişmiş özellikler", "price": 199, "currency": "TRY", "sort_order": 2},
        {"name": "Enterprise", "slug": "enterprise", "description": "Kurumsal paket", "price": 399, "currency": "TRY", "sort_order": 3},
    ]
    for p in plans:
        SubscriptionPlan.objects.get_or_create(slug=p["slug"], defaults=p)


def reverse_default_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(slug__in=["basic", "pro", "enterprise"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_plans, reverse_default_plans),
    ]
