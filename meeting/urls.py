from django.urls import path
from meeting.views import ScheduleMeetingView

urlpatterns = [
    path("", ScheduleMeetingView.as_view(), name="schedule-meeting"),
]
