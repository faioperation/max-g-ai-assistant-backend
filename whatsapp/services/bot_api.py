import requests
from django.conf import settings


class BotAPI:
    def __init__(self):
        self.bot_url = settings.BOT_URL
        self.api_key = settings.BOT_X_API_KEY
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

    def forward_to_bot(
        self,
        sender_number,
        message_text,
        sender_name="User",
        message_type="text",
        media_url=None,
    ):
        if not self.bot_url or not self.api_key:
            return "Bot is not configured."

        import datetime

        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "sender_number": sender_number,
            "sender_name": sender_name or "User",
            "message_body": message_text,
            "message_type": message_type,
            "platform": "whatsapp",
            "media_url": media_url,
            "timestamp": timestamp,
        }

        try:
            response = requests.post(
                self.bot_url, headers=self.headers, json=payload, timeout=45
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("reply", "No reply from bot.")
            else:
                return f"Bot error: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Bot connection error: {str(e)}"
