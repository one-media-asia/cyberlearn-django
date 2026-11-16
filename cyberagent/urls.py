from django.urls import path

from . import views, josh, relay

urlpatterns = [
    path("trial/start/", views.trial_start, name="trial_start"),
    path("josh/chat/", josh.chat, name="josh_chat"),
    path("relay/", relay.chat, name="cyberagent_relay"),
]
