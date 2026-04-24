from django.http import HttpResponse
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from django.conf import settings
from rest_framework.views import APIView
from whatsapp.services.meta_api import MetaAPI
from whatsapp.services.webhook_handler import WebhookHandler
from whatsapp.models import WhatsAppContact, WhatsAppMessage
from whatsapp.serializers import (
    ReplyDirectSerializer,
    ReplyMaxSerializer,
    ReplyResultsSerializer,
    ReplyResponseSerializer,
)
from whatsapp.services.formatter import ResultsFormatter

import logging
import requests

logger = logging.getLogger(__name__)


class PlainTextJSONParser(JSONParser):
    """Accepts application/json bodies sent with text/plain Content-Type (VPS bots)."""

    media_type = "text/plain"


BOT_PARSERS = [JSONParser, PlainTextJSONParser, FormParser, MultiPartParser]


def _do_send(meta_api, to, data):
    """Dispatch a WhatsApp message via Meta API. Returns (meta_response, error_response)."""
    msg_type = data["message_type"]
    body = data.get("body", "")
    media_url = data.get("media_url")

    if msg_type == "text":
        if not body:
            return None, Response(
                {"error": "body is required for message_type=text"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return meta_api.send_text_message(to, body), None
    else:
        if not media_url:
            return None, Response(
                {"error": f"media_url is required for message_type={msg_type}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return meta_api.send_media_message(to, msg_type, media_url=media_url), None


def _save_outgoing(contact_phone, data, wa_message_id):
    """Persist an outgoing message to the DB."""
    contact, _ = WhatsAppContact.objects.get_or_create(phone_number=contact_phone)
    WhatsAppMessage.objects.create(
        contact=contact,
        direction="out",
        message_type=data["message_type"],
        body=data.get("body", ""),
        media_url=data.get("media_url"),
        wa_message_id=wa_message_id,
        status="sent",
    )


# ─── Webhook ──────────────────────────────────────────────────────────────────


class WhatsAppWebhookView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Meta Webhook Verification",
        operation_description=(
            "Used by Meta to verify ownership of the webhook endpoint. "
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
                description="Your META_VERIFY_TOKEN",
            ),
            openapi.Parameter(
                "hub.challenge",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Random challenge from Meta",
            ),
        ],
        responses={
            200: openapi.Response("Returns hub.challenge"),
            403: openapi.Response("Invalid token"),
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
            "Meta posts all incoming events here. "
            "Saves the message to DB and forwards it to the AI bot.\n\n"
            "**Must return 200 within 5 s or Meta will retry.**"
        ),
        tags=["WhatsApp Webhook"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT, description="Standard Meta Webhook payload"
        ),
        responses={200: openapi.Response("Acknowledged")},
    )
    def post(self, request):
        WebhookHandler().process_webhook(request.data, request=request)
        return Response({"status": "received"}, status=status.HTTP_200_OK)


# ─── Reply endpoints ───────────────────────────────────────────────────────────


class ReplyDirectView(APIView):
    permission_classes = []
    parser_classes = BOT_PARSERS

    @swagger_auto_schema(
        operation_summary="Send reply to a WhatsApp user",
        operation_description=(
            "Called by the AI agent to send a message to a WhatsApp user.\n\n"
            "**Message types:** `text` (requires `body`) | `image/video/audio/document` (requires `media_url`)\n\n"
            "### Example Request\n"
            "```json\n"
            '{ "to": "8801641697469", "message_type": "text", "body": "Your flight is confirmed!" }\n'
            "```\n\n"
            "### Example Response\n"
            '```json\n{ "status": "sent", "wa_message_id": "wamid.HBg...", "to": "8801641697469" }\n```'
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
        meta_response, err = _do_send(MetaAPI(), to, serializer.validated_data)
        if err:
            return err

        if "messages" in meta_response:
            wa_id = meta_response["messages"][0].get("id")
            _save_outgoing(to, serializer.validated_data, wa_id)
            return Response(
                {"status": "sent", "wa_message_id": wa_id, "to": to},
                status=status.HTTP_200_OK,
            )

        return Response(meta_response, status=status.HTTP_502_BAD_GATEWAY)


class ReplyMaxView(APIView):
    permission_classes = []
    parser_classes = BOT_PARSERS

    @swagger_auto_schema(
        operation_summary="Send notification to Max (admin)",
        operation_description=(
            "Called by the AI agent to send a WhatsApp message to the admin number (`WHATSAPP_ADMIN_NUMBER`).\n\n"
            "No `to` field needed — recipient is always the admin.\n\n"
            "**Message types:** `text` (requires `body`) | `image/video/audio/document` (requires `media_url`)\n\n"
            "### Example Request\n"
            "```json\n"
            '{ "message_type": "text", "body": "Alert: user needs help!" }\n'
            "```\n\n"
            "### Example Response\n"
            '```json\n{ "status": "sent", "wa_message_id": "wamid.HBg...", "to": "880..." }\n```'
        ),
        tags=["WhatsApp Reply"],
        request_body=ReplyMaxSerializer,
        responses={
            200: ReplyResponseSerializer,
            400: openapi.Response("Validation error"),
            503: openapi.Response("Admin number not set"),
            502: openapi.Response("Meta API error"),
        },
    )
    def post(self, request):
        admin = settings.WHATSAPP_ADMIN_NUMBER
        if not admin:
            return Response(
                {"error": "WHATSAPP_ADMIN_NUMBER not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = ReplyMaxSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        meta_response, err = _do_send(MetaAPI(), admin, serializer.validated_data)
        if err:
            return err

        if "messages" in meta_response:
            wa_id = meta_response["messages"][0].get("id")
            _save_outgoing(admin, serializer.validated_data, wa_id)
            return Response(
                {"status": "sent", "wa_message_id": wa_id, "to": admin},
                status=status.HTTP_200_OK,
            )

        return Response(meta_response, status=status.HTTP_502_BAD_GATEWAY)


class ReplyResultsView(APIView):
    permission_classes = []
    parser_classes = BOT_PARSERS

    @swagger_auto_schema(
        operation_summary="Send formatted search results to user",
        operation_description=(
            "Takes a JSON list of flight offers or hotel search results, formats them as text, "
            "and sends them to the WhatsApp user. "
            "Large lists are automatically split into multiple messages based on `chunk_size`.\n\n"
            "### Example Request\n"
            "```json\n"
            "{\n"
            '  "to": "8801641697469",\n'
            '  "result_type": "flights",\n'
            '  "data": [... JSON from search ...],\n'
            '  "chunk_size": 5\n'
            "}\n"
            "```"
        ),
        tags=["WhatsApp Reply"],
        request_body=ReplyResultsSerializer,
        responses={
            200: openapi.Response("Results sent successfully"),
            400: openapi.Response("Validation error"),
        },
    )
    def post(self, request):
        serializer = ReplyResultsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        to = serializer.validated_data["to"]
        result_type = serializer.validated_data["result_type"]
        data = serializer.validated_data["data"]
        chunk_size = serializer.validated_data["chunk_size"]

        if result_type == "flights":
            chunks = ResultsFormatter.format_flights(data, chunk_size=chunk_size)
        else:
            chunks = ResultsFormatter.format_hotels(data, chunk_size=chunk_size)

        meta_api = MetaAPI()
        wa_ids = []
        for text in chunks:
            res = meta_api.send_text_message(to, text)
            if "messages" in res:
                wa_id = res["messages"][0].get("id")
                wa_ids.append(wa_id)
                # Save outgoing message
                _save_outgoing(to, {"message_type": "text", "body": text}, wa_id)

        return Response(
            {
                "status": "success",
                "messages_sent": len(chunks),
                "wa_message_ids": wa_ids,
                "to": to,
            },
            status=status.HTTP_200_OK,
        )


# ─── Media Proxy ──────────────────────────────────────────────────────────────


class MediaProxyView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Stream Meta media file",
        operation_description=(
            "Proxies a media file from Meta's CDN. "
            "Avoids exposing the Meta access token to clients."
        ),
        tags=["WhatsApp Media"],
        manual_parameters=[
            openapi.Parameter(
                "media_id",
                openapi.IN_PATH,
                type=openapi.TYPE_STRING,
                description="Meta media ID",
            ),
        ],
        responses={
            200: openapi.Response("Raw file binary"),
            404: openapi.Response("Not found"),
            502: openapi.Response("CDN fetch failed"),
        },
    )
    def get(self, request, media_id):
        media_info = MetaAPI().get_media_url(media_id)
        url = media_info.get("url")
        if not url:
            return Response(
                {"error": "Media not found"}, status=status.HTTP_404_NOT_FOUND
            )

        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {settings.META_ACCESS_TOKEN}"},
            stream=True,
        )
        if resp.status_code == 200:
            return HttpResponse(
                resp.iter_content(chunk_size=8192),
                content_type=resp.headers.get("Content-Type"),
            )
        return Response(
            {"error": "Failed to fetch media from Meta"},
            status=status.HTTP_502_BAD_GATEWAY,
        )
