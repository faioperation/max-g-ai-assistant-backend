from django.urls import path
from .views import ScheduleMeetingView

urlpatterns = [
    path("", ScheduleMeetingView.as_view(), name="schedule-meeting"),
]
