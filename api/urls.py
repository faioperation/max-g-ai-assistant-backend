from django.urls import path, include

urlpatterns = [
    path("whatsapp/", include("whatsapp.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("travel/", include("travel.urls")),
    path("meeting-schedule/", include("meeting.urls")),
]
