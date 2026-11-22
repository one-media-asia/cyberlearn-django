# Generated manually for manual Revolut donation recording.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cyberagent", "0005_donationsettings")]

    operations = [
        migrations.AddField(
            model_name="donation",
            name="payment_method",
            field=models.CharField(
                choices=[("stripe", "Stripe"), ("revolut_link", "Revolut.me"), ("revolut_transfer", "Revolut bank transfer"), ("bank_transfer", "Other bank transfer")],
                default="stripe",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="donation",
            name="manual_reference",
            field=models.CharField(blank=True, max_length=120, null=True, unique=True),
        ),
    ]
