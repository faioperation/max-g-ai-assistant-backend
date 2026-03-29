import requests
import os
from django.conf import settings

class MetaAPI:
    def __init__(self):
        self.access_token = settings.META_ACCESS_TOKEN
        self.phone_number_id = settings.META_PHONE_NUMBER_ID
        self.base_url = f"https://graph.facebook.com/v21.0/{self.phone_number_id}"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def send_text_message(self, to, text):
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        response = requests.post(url, headers=self.headers, json=payload)
        return response.json()

    def send_media_message(self, to, media_type, media_id=None, media_url=None):
        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": media_type,
        }
        
        if media_id:
            payload[media_type] = {"id": media_id}
        elif media_url:
            payload[media_type] = {"link": media_url}
        else:
            raise ValueError("Either media_id or media_url must be provided")

        response = requests.post(url, headers=self.headers, json=payload)
        return response.json()

    def upload_media(self, file_path, mime_type):
        url = f"{self.base_url}/media"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        with open(file_path, "rb") as f:
            files = {
                "file": (os.path.basename(file_path), f, mime_type),
            }
            data = {
                "messaging_product": "whatsapp",
                "type": mime_type.split("/")[0],
            }
            response = requests.post(url, headers=headers, files=files, data=data)
        return response.json()

    def get_media_url(self, media_id):
        url = f"https://graph.facebook.com/v21.0/{media_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.get(url, headers=headers)
        return response.json()
