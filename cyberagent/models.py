import uuid
from decimal import Decimal

from django.db import models


class TrialUsage(models.Model):
    session_key = models.CharField(max_length=40, unique=True)
    supabase_user_id = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
    )
    prompts_used = models.PositiveSmallIntegerField(default=0)
    paid_access = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        identity = str(self.supabase_user_id) if self.supabase_user_id else self.session_key[:8]
        return f"{identity} — {self.prompts_used} prompts"

class Donation(models.Model):
    class Interval(models.TextChoices):
        ONCE = "once", "One-time"
        MONTH = "month", "Monthly"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        ACTIVE = "active", "Monthly active"
        PAST_DUE = "past_due", "Payment past due"
        CANCELED = "canceled", "Canceled"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="eur")
    interval = models.CharField(max_length=8, choices=Interval.choices, default=Interval.ONCE)
    donor_name = models.CharField(max_length=120, blank=True)
    donor_email = models.EmailField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)

    class PaymentMethod(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        REVOLUT_LINK = "revolut_link", "Revolut.me"
        REVOLUT_TRANSFER = "revolut_transfer", "Revolut bank transfer"
        BANK_TRANSFER = "bank_transfer", "Other bank transfer"

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.STRIPE)
    manual_reference = models.CharField(max_length=120, unique=True, null=True, blank=True)
    stripe_checkout_session_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    stripe_invoice_id = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.currency.upper()} {self.amount} — {self.get_status_display()}"


class StripeWebhookEvent(models.Model):
    stripe_event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=120)
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} ({self.stripe_event_id})"



class DonationPayment(models.Model):
    """A single settled payment from a Donation Checkout or subscription invoice."""
    donation = models.ForeignKey(Donation, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="eur")
    stripe_invoice_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_checkout_session_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.currency.upper()} {self.amount} — donation {self.donation_id}"


class DonationSettings(models.Model):
    """Public fundraising configuration managed in Django admin."""
    fundraising_target = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("500.00"))
    currency = models.CharField(max_length=3, default="eur")

    class Meta:
        verbose_name = "Donation settings"
        verbose_name_plural = "Donation settings"

    def __str__(self):
        return f"Fundraising goal: {self.currency.upper()} {self.fundraising_target}"
