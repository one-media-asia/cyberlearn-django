import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cyberagent", "0003_donation_stripewebhookevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="DonationPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("refunded_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("currency", models.CharField(default="eur", max_length=3)),
                ("stripe_invoice_id", models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ("stripe_checkout_session_id", models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ("stripe_payment_intent_id", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("donation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="cyberagent.donation")),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
