import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cyberagent", "0002_trialusage_supabase_user_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="Donation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="eur", max_length=3)),
                ("interval", models.CharField(choices=[("once", "One-time"), ("month", "Monthly")], default="once", max_length=8)),
                ("donor_name", models.CharField(blank=True, max_length=120)),
                ("donor_email", models.EmailField(blank=True, max_length=254)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("paid", "Paid"), ("active", "Monthly active"), ("past_due", "Payment past due"), ("canceled", "Canceled"), ("failed", "Failed"), ("refunded", "Refunded")], default="pending", max_length=12)),
                ("stripe_checkout_session_id", models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ("stripe_customer_id", models.CharField(blank=True, max_length=255)),
                ("stripe_payment_intent_id", models.CharField(blank=True, max_length=255)),
                ("stripe_subscription_id", models.CharField(blank=True, max_length=255)),
                ("stripe_invoice_id", models.CharField(blank=True, max_length=255)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="StripeWebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stripe_event_id", models.CharField(max_length=255, unique=True)),
                ("event_type", models.CharField(max_length=120)),
                ("processed_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
