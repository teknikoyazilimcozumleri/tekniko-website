from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0002_default_plans"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="subscription_checkout_token",
            field=models.CharField(blank=True, db_index=True, max_length=500),
        ),
    ]
