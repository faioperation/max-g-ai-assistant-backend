from django.urls import path
from whatsapp.views import (
    WhatsAppWebhookView,
    MediaProxyView,
    ReplyDirectView,
    ReplyMaxView,
    ReplyResultsView,
)

urlpatterns = [
    path("webhook/", WhatsAppWebhookView.as_view(), name="whatsapp-webhook"),
    path("media/<str:media_id>/", MediaProxyView.as_view(), name="media-proxy"),
    path("reply/direct/", ReplyDirectView.as_view(), name="reply-direct"),
    path("reply/max/", ReplyMaxView.as_view(), name="reply-max"),
    path("reply/results/", ReplyResultsView.as_view(), name="reply-results"),
]
