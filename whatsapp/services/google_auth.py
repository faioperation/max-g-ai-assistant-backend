import os.path
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from django.conf import settings

logger = logging.getLogger(__name__)

# Combined scopes for both Calendar and Drive
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.file"
]

class GoogleAuthBase:
    """
    Base class to handle shared Google OAuth authentication.
    Used by both Calendar and Drive services.
    """
    def __init__(self):
        self.creds_path = settings.GOOGLE_CALENDAR_CREDENTIALS_PATH
        self.token_path = getattr(settings, "GOOGLE_CALENDAR_TOKEN_PATH", "token.json")
        self.creds = self._get_credentials()

    def _get_credentials(self):
        creds = None
        # Load from existing token.json
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # If no valid credentials, refresh or start flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Error refreshing Google token: {str(e)}")
                    creds = None

            if not creds:
                if not os.path.exists(self.creds_path):
                    logger.error(f"Credentials file not found at {self.creds_path}")
                    return None

                # Start local server flow for authentication
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.creds_path, SCOPES
                )
                # Note: This will block and wait for user to authorize in browser
                creds = flow.run_local_server(port=0)

            # Save the new token.json
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        return creds
