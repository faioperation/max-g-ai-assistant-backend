from rest_framework import serializers

class ScheduleMeetingSerializer(serializers.Serializer):
    title = serializers.CharField(
        max_length=255,
        help_text="Title/summary of the meeting"
    )
    start_datetime = serializers.DateTimeField(
        help_text="Meeting start time in ISO 8601 format (e.g. 2026-04-01T10:00:00Z)"
    )
    end_datetime = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Meeting end time. If omitted, defaults to 30 minutes after start."
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional description or agenda for the meeting"
    )
    location = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="Optional physical location (e.g. 'Office Room 2')"
    )
    attendee_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        help_text="Email of the user to send a calendar invite to"
    )

class MeetingResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    event_id = serializers.CharField()
    html_link = serializers.URLField()
    meet_link = serializers.URLField(allow_null=True)
    title = serializers.CharField()
    start_datetime = serializers.DateTimeField()
    end_datetime = serializers.DateTimeField()
