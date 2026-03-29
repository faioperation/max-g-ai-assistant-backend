import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import ScheduleMeetingSerializer, MeetingResponseSerializer
from .services.calendar_api import CalendarService

class ScheduleMeetingView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Schedule a Google Calendar meeting with Meet link",
        operation_description=(
            "Creates a Google Calendar event with a Google Meet link.\n\n"
            "If `attendee_email` is provided, an invite email will automatically be sent to that address.\n\n"
            "**Example request:**\n"
            "```json\n"
            "{\n"
            '  "title": "Project Sync",\n'
            '  "start_datetime": "2026-04-01T10:00:00Z",\n'
            '  "attendee_email": "user@example.com"\n'
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
        description = data.get("description", "")
        location = data.get("location", "")
        attendee_email = data.get("attendee_email", None)

        service = CalendarService()
        result = service.create_event(
            summary=title,
            start_time=start_dt,
            end_time=end_dt,
            description=description,
            location=location,
            attendee_email=attendee_email,
        )

        if "error" in result:
            return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "status": "success",
                "event_id": result.get("event_id"),
                "html_link": result.get("html_link"),
                "meet_link": result.get("meet_link"),
                "title": title,
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
