from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cyberagent", "0004_donationpayment"),
    ]

    operations = [
        migrations.CreateModel(
            name="DonationSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fundraising_target", models.DecimalField(decimal_places=2, default=Decimal("500.00"), max_digits=10)),
                ("currency", models.CharField(default="eur", max_length=3)),
            ],
            options={
                "verbose_name": "Donation settings",
                "verbose_name_plural": "Donation settings",
            },
        ),
    ]
