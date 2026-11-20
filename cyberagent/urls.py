from django.urls import path

from . import views, josh, relay, payments

urlpatterns = [
    path("trial/start/", views.trial_start, name="trial_start"),
    path("josh/chat/", josh.chat, name="josh_chat"),
    path("relay/", relay.chat, name="cyberagent_relay"),
    path("donations/stats/", payments.donation_stats, name="donation_stats"),
    path("donations/checkout/", payments.create_donation_checkout, name="donation_checkout"),
    path("donations/webhook/", payments.stripe_webhook, name="stripe_donation_webhook"),
    path("donations/portal/", payments.create_donation_portal_session, name="donation_portal_session"),
]
