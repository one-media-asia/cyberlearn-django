import json
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import stripe
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Donation, StripeWebhookEvent

logger = logging.getLogger(__name__)

MIN_DONATION = Decimal("1.00")
MAX_DONATION = Decimal("10000.00")


def _stripe_client():
    key = getattr(settings, "STRIPE_SECRET_KEY", "")
    if not key:
        raise RuntimeError("Stripe is not configured.")
    return stripe.StripeClient(key)


def _checkout_session_paid(session):
    return session.get("payment_status") == "paid"


@csrf_exempt
@require_POST
def create_donation_checkout(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request body."}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Invalid request body."}, status=400)

    # A lightweight per-IP limit. Add an edge/WAF limit before public launch.
    ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
    ip = ip or request.META.get("REMOTE_ADDR", "unknown")
    cache_key = f"donation-checkout:{ip}"
    if not cache.add(cache_key, 1, timeout=3600):
        try:
            attempts = cache.incr(cache_key)
        except ValueError:
            attempts = 1
            cache.set(cache_key, attempts, timeout=3600)
        if attempts > 10:
            return JsonResponse({"error": "Too many attempts. Please try again later."}, status=429)

    try:
        amount = Decimal(str(data.get("amount", ""))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, ValueError, TypeError):
        return JsonResponse({"error": "Enter a valid donation amount."}, status=400)

    if not amount.is_finite() or amount < MIN_DONATION or amount > MAX_DONATION:
        return JsonResponse(
            {"error": "Donations must be between €1.00 and €10,000.00."},
            status=400,
        )

    interval = data.get("interval", "once")
    if interval not in ("once", "month"):
        return JsonResponse({"error": "Choose a one-time or monthly donation."}, status=400)

    donor_name = str(data.get("name", "")).strip()[:120]
    donor_email = str(data.get("email", "")).strip()[:254]
    if donor_email:
        try:
            validate_email(donor_email)
        except ValidationError:
            return JsonResponse({"error": "Enter a valid email address."}, status=400)

    frontend_url = getattr(settings, "DONATION_FRONTEND_URL", "").rstrip("/")
    if not frontend_url:
        return JsonResponse({"error": "Donation checkout is not configured."}, status=503)

    donation = Donation.objects.create(
        amount=amount,
        currency="eur",
        interval=interval,
        donor_name=donor_name,
        donor_email=donor_email,
        status=Donation.Status.PENDING,
    )

    try:
        client = _stripe_client()
        product_name = (
            "CyberLearn Monthly Support"
            if interval == "month"
            else "CyberLearn Donation"
        )
        price_data = {
            "currency": "eur",
            "unit_amount": int(amount * 100),
            # Donor-entered amount is the tax-inclusive total.
            "tax_behavior": "inclusive",
            "product_data": {
                "name": product_name,
                "description": "Voluntary support for CyberLearn cybersecurity education.",
            },
        }
        params = {
            "mode": "subscription" if interval == "month" else "payment",
            # Stripe Tax calculates applicable tax; inclusive pricing keeps the
            # displayed Checkout total at the amount selected by the donor.
            "automatic_tax": {"enabled": True},
            "line_items": [{
                "price_data": (
                    {**price_data, "recurring": {"interval": "month"}}
                    if interval == "month"
                    else price_data
                ),
                "quantity": 1,
            }],
            "success_url": f"{frontend_url}/donate/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{frontend_url}/donate?cancelled=1",
            "client_reference_id": str(donation.id),
            "metadata": {"donation_id": str(donation.id), "purpose": "cyberlearn_support"},
        }
        if donor_email:
            params["customer_email"] = donor_email
        if interval == "month":
            params["subscription_data"] = {
                "description": "Monthly voluntary support for CyberLearn",
                "metadata": {"donation_id": str(donation.id)},
            }
        else:
            # The paid Checkout payment creates its invoice; do not create a
            # second payable invoice through the Invoicing API.
            params["customer_creation"] = "always"
            params["invoice_creation"] = {
                "enabled": True,
                "invoice_data": {
                    "description": "Voluntary support for CyberLearn",
                    "metadata": {"donation_id": str(donation.id)},
                },
            }

        session = client.v1.checkout.sessions.create(params)
        donation.stripe_checkout_session_id = session.id
        donation.save(update_fields=["stripe_checkout_session_id", "updated_at"])
        return JsonResponse({"checkout_url": session.url})
    except Exception:
        logger.exception("Unable to create Stripe Checkout Session for donation %s", donation.id)
        donation.status = Donation.Status.FAILED
        donation.save(update_fields=["status", "updated_at"])
        return JsonResponse(
            {"error": "We could not start checkout. Please try again."},
            status=502,
        )


def _complete_checkout(session):
    if not _checkout_session_paid(session):
        return
    donation_id = (session.get("metadata") or {}).get("donation_id")
    if not donation_id:
        return
    try:
        donation = Donation.objects.select_for_update().get(id=donation_id)
    except Donation.DoesNotExist:
        logger.warning("Stripe Checkout Session references unknown donation %s", donation_id)
        return

    details = session.get("customer_details") or {}
    donation.status = (
        Donation.Status.ACTIVE
        if donation.interval == Donation.Interval.MONTH
        else Donation.Status.PAID
    )
    donation.stripe_customer_id = session.get("customer") or donation.stripe_customer_id
    donation.stripe_payment_intent_id = session.get("payment_intent") or donation.stripe_payment_intent_id
    donation.stripe_subscription_id = session.get("subscription") or donation.stripe_subscription_id
    donation.stripe_invoice_id = session.get("invoice") or donation.stripe_invoice_id
    donation.donor_email = details.get("email") or donation.donor_email
    donation.donor_name = details.get("name") or donation.donor_name
    donation.paid_at = donation.paid_at or timezone.now()
    donation.save()


def _subscription_id_from_invoice(invoice):
    direct = invoice.get("subscription")
    if direct:
        return direct
    parent = invoice.get("parent") or {}
    details = parent.get("subscription_details") or {}
    return details.get("subscription")


@csrf_exempt
@require_POST
def stripe_webhook(request):
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        return JsonResponse({"error": "Webhook is not configured."}, status=503)

    signature = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(request.body, signature, secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return JsonResponse({"error": "Invalid webhook signature."}, status=400)

    event_id = event["id"]
    event_type = event["type"]
    obj = event["data"]["object"]

    try:
        with transaction.atomic():
            if StripeWebhookEvent.objects.filter(stripe_event_id=event_id).exists():
                return JsonResponse({"received": True, "duplicate": True})

            if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
                _complete_checkout(obj)
            elif event_type == "checkout.session.async_payment_failed":
                donation_id = (obj.get("metadata") or {}).get("donation_id")
                Donation.objects.filter(id=donation_id, status=Donation.Status.PENDING).update(
                    status=Donation.Status.FAILED
                )
            elif event_type == "invoice.paid":
                subscription_id = _subscription_id_from_invoice(obj)
                if subscription_id:
                    Donation.objects.filter(stripe_subscription_id=subscription_id).update(
                        status=Donation.Status.ACTIVE,
                        stripe_invoice_id=obj.get("id", ""),
                    )
            elif event_type == "invoice.payment_failed":
                subscription_id = _subscription_id_from_invoice(obj)
                if subscription_id:
                    Donation.objects.filter(stripe_subscription_id=subscription_id).update(
                        status=Donation.Status.PAST_DUE,
                        stripe_invoice_id=obj.get("id", ""),
                    )
            elif event_type == "customer.subscription.deleted":
                Donation.objects.filter(stripe_subscription_id=obj.get("id")).update(
                    status=Donation.Status.CANCELED
                )
            elif event_type == "charge.refunded":
                payment_intent = obj.get("payment_intent")
                if payment_intent:
                    Donation.objects.filter(stripe_payment_intent_id=payment_intent).update(
                        status=Donation.Status.REFUNDED
                    )

            StripeWebhookEvent.objects.create(
                stripe_event_id=event_id,
                event_type=event_type,
            )
    except Exception:
        logger.exception("Failed to process Stripe webhook event %s", event_id)
        return JsonResponse({"error": "Webhook processing failed."}, status=500)

    return JsonResponse({"received": True})

