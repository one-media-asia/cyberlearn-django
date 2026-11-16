from django.contrib import admin

from .models import Donation, StripeWebhookEvent, TrialUsage


@admin.register(TrialUsage)
class TrialUsageAdmin(admin.ModelAdmin):
    list_display = ("session_key", "prompts_used", "paid_access", "created_at", "updated_at")
    list_filter = ("paid_access", "created_at")
    search_fields = ("session_key",)
    readonly_fields = ("session_key", "created_at", "updated_at")


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "donor_email", "amount", "currency", "interval", "status")
    list_filter = ("status", "interval", "currency", "created_at")
    search_fields = ("donor_name", "donor_email", "stripe_checkout_session_id", "stripe_customer_id")
    readonly_fields = (
        "id", "stripe_checkout_session_id", "stripe_customer_id",
        "stripe_payment_intent_id", "stripe_subscription_id",
        "stripe_invoice_id", "paid_at", "created_at", "updated_at",
    )


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("stripe_event_id", "event_type", "processed_at")
    search_fields = ("stripe_event_id", "event_type")
    readonly_fields = ("stripe_event_id", "event_type", "processed_at")
