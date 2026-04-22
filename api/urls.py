from django.urls import path, include
from api.views import DuffelUnifiedWebhookView

urlpatterns = [
    path("whatsapp/", include("whatsapp.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("travel/", include("travel.urls")),
    path("stays/", include("stays.urls")),
    path("meeting-schedule/", include("meeting.urls")),
    path("duffel-webhook/", DuffelUnifiedWebhookView.as_view(), name="duffel-webhook"),
]
