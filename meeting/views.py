import datetime
import pytz
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from meeting.serializers import ScheduleMeetingSerializer, MeetingResponseSerializer
from meeting.services.calendar_api import CalendarService


class ScheduleMeetingView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Schedule a Google Calendar meeting with Meet link",
        operation_description=(
            "Creates a Google Calendar event with a Google Meet link.\n\n"
            "If `attendee_emails` is provided, an invite email will automatically be sent to those addresses.\n\n"
            "All meeting times are treated as United Arab Emirates (Asia/Dubai) timezone.\n\n"
            "### Example Request Payload\n"
            "```json\n"
            "{\n"
            '  "title": "Project Sync",\n'
            '  "start_datetime": "2026-05-01 10:30",\n'
            '  "end_datetime": "2026-05-01 11:00",\n'
            '  "description": "Q2 Planning and sync",\n'
            '  "location": "Google Meet",\n'
            '  "attendee_emails": ["user1@example.com", "user2@example.com"]\n'
            "}\n"
            "```\n\n"
            "### Example Response Payload\n"
            "```json\n"
            "{\n"
            '  "status": "success",\n'
            '  "event_id": "abc123xyz...",\n'
            '  "calendar_link": "https://calendar.google.com/calendar/event?eid=...",\n'
            '  "meet_link": "https://meet.google.com/abc-defg-hij",\n'
            '  "title": "Project Sync",\n'
            '  "start_datetime": "2026-05-01T10:30:00+04:00",\n'
            '  "end_datetime": "2026-05-01T11:00:00+04:00"\n'
            "}\n"
            "```"
        ),
        tags=["Meeting"],
        request_body=ScheduleMeetingSerializer,
        responses={
            200: MeetingResponseSerializer,
            400: openapi.Response("Validation error"),
            503: openapi.Response("Google Calendar not configured or auth failed"),
        },
    )
    def post(self, request):
        serializer = ScheduleMeetingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        title = data["title"]
        start_dt = data["start_datetime"]
        end_dt = data.get("end_datetime") or (start_dt + datetime.timedelta(minutes=30))
        
        # Ensure UAE timezone if naive
        uae_tz = pytz.timezone("Asia/Dubai")
        if start_dt.tzinfo is None:
            start_dt = uae_tz.localize(start_dt)
        if end_dt.tzinfo is None:
            end_dt = uae_tz.localize(end_dt)

        description = data.get("description", "")
        location = data.get("location", "")
        attendee_emails = data.get("attendee_emails", [])

        service = CalendarService()
        result = service.create_event(
            summary=title,
            start_time=start_dt,
            end_time=end_dt,
            description=description,
            location=location,
            attendee_emails=attendee_emails,
        )

        if "error" in result:
            return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "status": "success",
                "event_id": result.get("event_id"),
                "calendar_link": result.get("html_link"),
                "meet_link": result.get("meet_link"),
                "title": title,
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
