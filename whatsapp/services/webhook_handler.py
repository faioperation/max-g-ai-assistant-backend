import logging
from whatsapp.services.meta_api import MetaAPI
from whatsapp.services.bot_api import BotAPI
from whatsapp.models import WhatsAppContact, WhatsAppMessage

logger = logging.getLogger(__name__)


class WebhookHandler:
    def __init__(self):
        self.meta_api = MetaAPI()
        self.bot_api = BotAPI()

    def process_webhook(self, data, request=None):
        """
        Main entry point for processing the webhook payload.
        Saves messages to DB and forwards to AI bot — no auto-reply.
        The bot decides what to do and calls /reply/direct/ or /reply/max/.
        """
        try:
            entries = data.get("entry", [])
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    if "messages" in value:
                        self._handle_messages(value, request)
                    elif "statuses" in value:
                        self._handle_statuses(value)
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")

    def _handle_messages(self, value, request=None):
        contacts = value.get("contacts", [])
        messages = value.get("messages", [])

        for msg in messages:
            wa_id = msg.get("id")
            from_number = msg.get("from")
            msg_type = msg.get("type", "text")

            profile_name = (
                contacts[0].get("profile", {}).get("name") if contacts else None
            )
            contact, _ = WhatsAppContact.objects.get_or_create(
                phone_number=from_number,
                defaults={"profile_name": profile_name},
            )

            body = ""
            media_id = None
            mime_type = None
            proxy_url = None

            if msg_type == "text":
                body = msg.get("text", {}).get("body", "")
            elif msg_type in ["image", "video", "audio", "document"]:
                media_id = msg.get(msg_type, {}).get("id")
                mime_type = msg.get(msg_type, {}).get("mime_type")
                body = msg.get(msg_type, {}).get("caption", "")

                if media_id and request:
                    from django.urls import reverse

                    path = reverse("media-proxy", args=[media_id])
                    proxy_url = request.build_absolute_uri(path)

            if not body:
                body = f"[{msg_type.capitalize()} uploaded]"

            WhatsAppMessage.objects.create(
                contact=contact,
                direction="in",
                message_type=msg_type,
                body=body,
                media_id=media_id,
                media_url=proxy_url,
                media_mime_type=mime_type,
                wa_message_id=wa_id,
                status="delivered",
            )

            self.bot_api.forward_to_bot(
                sender_number=from_number,
                message_text=body,
                sender_name=profile_name,
                message_type=msg_type,
                media_url=proxy_url,
            )

    def _handle_statuses(self, value):
        statuses = value.get("statuses", [])
        for status in statuses:
            wa_id = status.get("id")
            status_val = status.get("status")
            try:
                msg = WhatsAppMessage.objects.get(wa_message_id=wa_id)
                msg.status = status_val
                msg.save()
            except WhatsAppMessage.DoesNotExist:
                pass
