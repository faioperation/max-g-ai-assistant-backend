import os.path
import datetime
import logging
import uuid
from whatsapp.services.google_auth import GoogleAuthBase
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from django.conf import settings
from dateutil.parser import parse as parse_date

logger = logging.getLogger(__name__)

class CalendarService(GoogleAuthBase):
    def __init__(self):
        super().__init__()
        self.calendar_id = settings.GOOGLE_CALENDAR_ID or "primary"

    def create_event(
        self,
        summary,
        start_time,
        end_time=None,
        description=None,
        location=None,
        attendee_emails=None,
    ):
        if not self.creds:
            return {"error": "Google Calendar authentication failed"}

        if not end_time:
            end_time = start_time + datetime.timedelta(minutes=30)

        try:
            service = build("calendar", "v3", credentials=self.creds)
            event = {
                "summary": summary,
                "location": location,
                "description": description,
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "Asia/Dubai",
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "Asia/Dubai",
                },
                "conferenceData": {
                    "createRequest": {
                        "requestId": str(uuid.uuid4()),
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
            }

            if attendee_emails:
                event["attendees"] = [{"email": email.strip()} for email in attendee_emails if email.strip()]

            event = (
                service.events()
                .insert(
                    calendarId=self.calendar_id,
                    body=event,
                    conferenceDataVersion=1,
                    sendUpdates="all" if attendee_emails else "none",
                )
                .execute()
            )

            meet_link = None
            if "conferenceData" in event and "entryPoints" in event["conferenceData"]:
                for entry in event["conferenceData"]["entryPoints"]:
                    if entry["entryPointType"] == "video":
                        meet_link = entry["uri"]
                        break

            return {
                "status": "success",
                "event_id": event.get("id"),
                "html_link": event.get("htmlLink"),
                "meet_link": meet_link,
            }

        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            return {"error": str(error)}

    def parse_and_schedule(self, text, attendee_emails=None):
        try:
            from django.utils import timezone
            dt = parse_date(text, fuzzy=True)
            # If naive, localize to the project's current timezone (Asia/Dubai)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)

            if dt < timezone.now():
                dt = dt + datetime.timedelta(days=1)

            summary = f"Meeting scheduled via Bot: {text[:50]}..."
            description = f"Original request: {text}"

            return self.create_event(
                summary, dt, description=description, attendee_emails=attendee_emails
            )
        except Exception as e:
            logger.error(f"Error parsing date from text: {str(e)}")
            return {"error": "Could not understand the date/time."}
