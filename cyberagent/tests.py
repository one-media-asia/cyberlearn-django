from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Donation
from .payments import _send_subscription_management_email


@override_settings(
    STRIPE_SECRET_KEY="sk_test_unit_test",
    DONATION_FRONTEND_URL="https://cyberlearn.onemedia.asia",
    DEFAULT_FROM_EMAIL="CyberLearn <noreply@example.test>",
)
class DonationManagementTests(TestCase):
    def setUp(self):
        self.donation = Donation.objects.create(
            amount="10.00",
            currency="eur",
            interval=Donation.Interval.MONTH,
            donor_name="Test Donor",
            donor_email="donor@example.test",
            status=Donation.Status.ACTIVE,
            stripe_customer_id="cus_test_123",
            stripe_subscription_id="sub_test_123",
        )

    def management_token(self, **overrides):
        payload = {
            "donation_id": str(self.donation.pk),
            "email": self.donation.donor_email,
        }
        payload.update(overrides)
        return signing.dumps(payload, salt="cyberlearn.donation.portal.v1")

    def test_portal_rejects_missing_token(self):
        response = self.client.post(
            reverse("donation_portal_session"),
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_portal_rejects_invalid_token(self):
        response = self.client.post(
            reverse("donation_portal_session"),
            data={"token": "not-a-valid-token"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_portal_rejects_token_for_different_email(self):
        token = self.management_token(email="attacker@example.test")
        response = self.client.post(
            reverse("donation_portal_session"),
            data={"token": token},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    @patch("cyberagent.payments._stripe_client")
    def test_valid_token_creates_portal_session_for_saved_customer(self, stripe_client):
        create_session = Mock(return_value=SimpleNamespace(url="https://billing.stripe.test/session"))
        stripe_client.return_value = SimpleNamespace(
            v1=SimpleNamespace(
                billing_portal=SimpleNamespace(
                    sessions=SimpleNamespace(create=create_session)
                )
            )
        )

        response = self.client.post(
            reverse("donation_portal_session"),
            data={"token": self.management_token()},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["portal_url"],
            "https://billing.stripe.test/session",
        )
        create_session.assert_called_once_with({
            "customer": "cus_test_123",
            "return_url": "https://cyberlearn.onemedia.asia/donate",
        })

    @patch("cyberagent.payments.send_mail")
    def test_monthly_management_email_contains_signed_link(self, send_mail_mock):
        _send_subscription_management_email(self.donation.pk)

        send_mail_mock.assert_called_once()
        args, kwargs = send_mail_mock.call_args
        self.assertEqual(kwargs["recipient_list"], ["donor@example.test"])
        self.assertIn("https://cyberlearn.onemedia.asia/donate/manage?token=", kwargs["message"])

    def test_checkout_rejects_amount_below_minimum(self):
        response = self.client.post(
            reverse("donation_checkout"),
            data={"amount": "0.50", "interval": "once"},
            content_type="application/json",
            REMOTE_ADDR="192.0.2.40",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Donation.objects.exclude(pk=self.donation.pk).exists())
