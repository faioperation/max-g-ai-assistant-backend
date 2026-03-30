from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from whatsapp.services.webhook_handler import WebhookHandler
from whatsapp.services.meta_api import MetaAPI
from whatsapp.models import WhatsAppContact, WhatsAppMessage
from whatsapp.serializers import (
    ReplyDirectSerializer,
    ReplyMaxSerializer,
    ReplyResponseSerializer,
)
import requests
import logging

logger = logging.getLogger(__name__)


# ─── Shared helpers ──────────────────────────────────────────────────────────


def _do_send(meta_api, to, serializer_data):
    """Send a message via Meta API and return (meta_response, error_response)."""
    msg_type = serializer_data["message_type"]
    body = serializer_data.get("body", "")
    media_url = serializer_data.get("media_url")
    caption = serializer_data.get("caption", "")

    if msg_type == "text":
        if not body:
            return None, Response(
                {"error": "body is required for message_type=text"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        meta_response = meta_api.send_text_message(to, body)
    else:
        if not media_url:
            return None, Response(
                {"error": f"media_url is required for message_type={msg_type}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        meta_response = meta_api.send_media_message(to, msg_type, media_url=media_url)

    return meta_response, None


# ─── Webhook ──────────────────────────────────────────────────────────────────


class WhatsAppWebhookView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Meta Webhook Verification",
        operation_description=(
            "Used by Meta to verify ownership of the webhook endpoint. "
            "Meta sends hub.mode, hub.verify_token, and hub.challenge as query params. "
            "Returns the hub.challenge value if the verify_token matches."
        ),
        tags=["WhatsApp Webhook"],
        manual_parameters=[
            openapi.Parameter(
                "hub.mode",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Should be 'subscribe'",
            ),
            openapi.Parameter(
                "hub.verify_token",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Your META_VERIFY_TOKEN from .env",
            ),
            openapi.Parameter(
                "hub.challenge",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Random challenge string from Meta",
            ),
        ],
        responses={
            200: openapi.Response(
                "Verification successful — returns hub.challenge value"
            ),
            403: openapi.Response("Invalid verify token"),
        },
    )
    def get(self, request):
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse("Verification failed", status=403)

    @swagger_auto_schema(
        operation_summary="Receive incoming WhatsApp messages",
        operation_description=(
            "Meta posts all incoming events here (messages, status updates, etc.). "
            "The handler saves the message to DB and forwards it to the AI bot. "
            "The bot then calls /reply/direct/ or /reply/max/ to respond.\n\n"
            "**This endpoint must return 200 within 5 s or Meta will retry.**"
        ),
        tags=["WhatsApp Webhook"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            description="Standard Meta Webhook payload",
        ),
        responses={
            200: openapi.Response("Acknowledged"),
        },
    )
    def post(self, request):
        handler = WebhookHandler()
        handler.process_webhook(request.data, request=request)
        return Response({"status": "received"}, status=status.HTTP_200_OK)


# ─── Reply endpoints (called by the AI Bot) ───────────────────────────────────


class ReplyDirectView(APIView):
    """
    Send a WhatsApp message directly to a specific user.
    Called by the AI bot when it wants to reply to the original sender.
    """

    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Send reply to a WhatsApp user",
        operation_description=(
            "Called by the AI agent to send a message directly to a WhatsApp user.\n\n"
            "**Message types:**\n"
            "- `text` — requires `body`\n"
            "- `image / video / audio / document` — requires `media_url` (publicly accessible)\n\n"
            "### Example Request Payload\n"
            "```json\n"
            "{\n"
            '  "to": "8801641697469",\n'
            '  "message_type": "text",\n'
            '  "body": "Here are your flight details!",\n'
            '  "media_url": null,\n'
            '  "caption": ""\n'
            "}\n"
            "```\n\n"
            "### Example Response Payload\n"
            "```json\n"
            "{\n"
            '  "status": "success",\n'
            '  "message": "Direct message sent to 8801641697469",\n'
            '  "wa_message_id": "wamid.HBg...",\n'
            '  "meta_response": { ... }\n'
            "}\n"
            "```"
        ),
        tags=["WhatsApp Reply"],
        request_body=ReplyDirectSerializer,
        responses={
            200: ReplyResponseSerializer,
            400: openapi.Response("Validation error"),
            502: openapi.Response("Meta API error"),
        },
    )
    def post(self, request):
        serializer = ReplyDirectSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        to = serializer.validated_data["to"]
        meta_api = MetaAPI()
        meta_response, err = _do_send(meta_api, to, serializer.validated_data)
        if err:
            return err

        wa_message_id = None
        if "messages" in meta_response:
            wa_message_id = meta_response["messages"][0].get("id")
            contact, _ = WhatsAppContact.objects.get_or_create(phone_number=to)
            WhatsAppMessage.objects.create(
                contact=contact,
                direction="out",
                message_type=serializer.validated_data["message_type"],
                body=serializer.validated_data.get("body", ""),
                media_url=serializer.validated_data.get("media_url"),
                wa_message_id=wa_message_id,
                status="sent",
            )
            return Response(
                {"status": "sent", "wa_message_id": wa_message_id, "to": to},
                status=status.HTTP_200_OK,
            )

        return Response(meta_response, status=status.HTTP_502_BAD_GATEWAY)


class ReplyMaxView(APIView):
    """
    Send a WhatsApp message to the admin number (Max).
    Called by the AI bot when it needs to notify the admin instead of (or in addition to) the user.
    """

    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Send notification to Max (admin)",
        operation_description=(
            "Called by the AI agent to send a message to the admin WhatsApp number "
            "configured as `WHATSAPP_ADMIN_NUMBER` in the environment.\n\n"
            "**No `to` field needed** — the recipient is always the admin number.\n\n"
            "**Message types:**\n"
            "- `text` — requires `body`\n"
            "- `image / video / audio / document` — requires `media_url` (publicly accessible)\n\n"
            "### Example Request Payload\n"
            "```json\n"
            "{\n"
            '  "message_type": "text",\n'
            '  "body": "Alert: The user needs human assistance!",\n'
            '  "media_url": null,\n'
            '  "caption": ""\n'
            "}\n"
            "```\n\n"
            "### Example Response Payload\n"
            "```json\n"
            "{\n"
            '  "status": "success",\n'
            '  "message": "Message sent to admin",\n'
            '  "wa_message_id": "wamid.HBg...",\n'
            '  "meta_response": { ... }\n'
            "}\n"
            "```"
        ),
        tags=["WhatsApp Reply"],
        request_body=ReplyMaxSerializer,
        responses={
            200: ReplyResponseSerializer,
            400: openapi.Response("Validation error"),
            503: openapi.Response("WHATSAPP_ADMIN_NUMBER not configured"),
            502: openapi.Response("Meta API error"),
        },
    )
    def post(self, request):
        admin_number = settings.WHATSAPP_ADMIN_NUMBER
        if not admin_number:
            return Response(
                {"error": "WHATSAPP_ADMIN_NUMBER is not configured in environment"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = ReplyMaxSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        meta_api = MetaAPI()
        meta_response, err = _do_send(meta_api, admin_number, serializer.validated_data)
        if err:
            return err

        wa_message_id = None
        if "messages" in meta_response:
            wa_message_id = meta_response["messages"][0].get("id")
            contact, _ = WhatsAppContact.objects.get_or_create(
                phone_number=admin_number
            )
            WhatsAppMessage.objects.create(
                contact=contact,
                direction="out",
                message_type=serializer.validated_data["message_type"],
                body=serializer.validated_data.get("body", ""),
                media_url=serializer.validated_data.get("media_url"),
                wa_message_id=wa_message_id,
                status="sent",
            )
            return Response(
                {"status": "sent", "wa_message_id": wa_message_id, "to": admin_number},
                status=status.HTTP_200_OK,
            )

        return Response(meta_response, status=status.HTTP_502_BAD_GATEWAY)


# ─── Media Proxy ──────────────────────────────────────────────────────────────


class MediaProxyView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Stream Meta media file",
        operation_description=(
            "Proxies a media file from Meta's CDN using the stored `media_id`. "
            "This avoids exposing the Meta access token to external clients. "
            "The response is the raw binary content of the file."
        ),
        tags=["WhatsApp Media"],
        manual_parameters=[
            openapi.Parameter(
                "media_id",
                openapi.IN_PATH,
                type=openapi.TYPE_STRING,
                description="Meta media ID (e.g. 1262574552048176)",
            )
        ],
        responses={
            200: openapi.Response("Raw binary file content"),
            404: openapi.Response("Media ID not found or URL not returned"),
            502: openapi.Response("Failed to fetch from Meta CDN"),
        },
    )
    def get(self, request, media_id):
        meta_api = MetaAPI()
        media_info = meta_api.get_media_url(media_id)
        url = media_info.get("url")
        if not url:
            return Response(
                {"error": "Media not found"}, status=status.HTTP_404_NOT_FOUND
            )

        headers = {"Authorization": f"Bearer {settings.META_ACCESS_TOKEN}"}
        response = requests.get(url, headers=headers, stream=True)
        if response.status_code == 200:
            return HttpResponse(
                response.iter_content(chunk_size=8192),
                content_type=response.headers.get("Content-Type"),
            )
        return Response(
            {"error": "Failed to fetch media from Meta"},
            status=status.HTTP_502_BAD_GATEWAY,
        )
