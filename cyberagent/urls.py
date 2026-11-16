from django.urls import path

from . import views, josh, relay, payments

urlpatterns = [
    path("trial/start/", views.trial_start, name="trial_start"),
    path("josh/chat/", josh.chat, name="josh_chat"),
    path("relay/", relay.chat, name="cyberagent_relay"),
    path("donations/checkout/", payments.create_donation_checkout, name="donation_checkout"),
    path("donations/webhook/", payments.stripe_webhook, name="stripe_donation_webhook"),
]
