from django.contrib import admin

from .models import Donation, DonationPayment, DonationSettings, StripeWebhookEvent, TrialUsage


@admin.register(TrialUsage)
class TrialUsageAdmin(admin.ModelAdmin):
    list_display = ("session_key", "prompts_used", "paid_access", "created_at", "updated_at")
    list_filter = ("paid_access", "created_at")
    search_fields = ("session_key",)
    readonly_fields = ("session_key", "created_at", "updated_at")


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "donor_email", "amount", "currency", "payment_method", "status")
    list_filter = ("status", "payment_method", "interval", "currency", "created_at")
    search_fields = ("donor_name", "donor_email", "manual_reference", "stripe_checkout_session_id", "stripe_customer_id")
    readonly_fields = (
        "id", "stripe_checkout_session_id", "stripe_customer_id",
        "stripe_payment_intent_id", "stripe_subscription_id",
        "stripe_invoice_id", "created_at", "updated_at",
    )
    fieldsets = (
        ("Donation", {"fields": ("amount", "currency", "interval", "donor_name", "donor_email", "status", "paid_at")}),
        ("Manual payment recording", {"fields": ("payment_method", "manual_reference")}),
        ("Stripe details (read-only)", {"fields": ("id", "stripe_checkout_session_id", "stripe_customer_id", "stripe_payment_intent_id", "stripe_subscription_id", "stripe_invoice_id", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        from uuid import uuid4
        from django.utils import timezone

        is_manual = obj.payment_method != Donation.PaymentMethod.STRIPE
        if is_manual and obj.status == Donation.Status.PAID:
            if not obj.paid_at:
                obj.paid_at = timezone.now()
            if not obj.manual_reference:
                obj.manual_reference = f"CYBERLEARN-{uuid4().hex[:10].upper()}"

        super().save_model(request, obj, form, change)

        if is_manual:
            payment = DonationPayment.objects.filter(
                donation=obj,
                stripe_invoice_id__isnull=True,
                stripe_checkout_session_id__isnull=True,
            ).first()
            if obj.status == Donation.Status.PAID:
                values = {"amount": obj.amount, "currency": obj.currency.lower(), "refunded_amount": 0}
                if payment:
                    for key, value in values.items():
                        setattr(payment, key, value)
                    payment.save(update_fields=list(values.keys()))
                else:
                    DonationPayment.objects.create(donation=obj, **values)
            elif payment:
                payment.delete()


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("stripe_event_id", "event_type", "processed_at")
    search_fields = ("stripe_event_id", "event_type")
    readonly_fields = ("stripe_event_id", "event_type", "processed_at")


@admin.register(DonationPayment)
class DonationPaymentAdmin(admin.ModelAdmin):
    list_display = ("created_at", "donation", "amount", "refunded_amount", "currency")
    list_filter = ("currency", "created_at")
    search_fields = ("stripe_invoice_id", "stripe_checkout_session_id", "stripe_payment_intent_id")
    fields = (
        "donation", "amount", "refunded_amount", "currency",
        "stripe_invoice_id", "stripe_checkout_session_id",
        "stripe_payment_intent_id", "created_at",
    )
    readonly_fields = ("created_at",)


@admin.register(DonationSettings)
class DonationSettingsAdmin(admin.ModelAdmin):
    list_display = ("fundraising_target", "currency")
    fields = ("fundraising_target", "currency")

    def has_add_permission(self, request):
        return not DonationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
