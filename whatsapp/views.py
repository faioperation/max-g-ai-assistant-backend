from django.http import HttpResponse
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework import status
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
)
from whatsapp.services.formatter import ResultsFormatter
from whatsapp.schemas import (
    WHATSAPP_WEBHOOK_VERIFY_SCHEMA,
    WHATSAPP_WEBHOOK_POST_SCHEMA,
    REPLY_DIRECT_SCHEMA,
    REPLY_MAX_SCHEMA,
    REPLY_RESULTS_SCHEMA,
    MEDIA_PROXY_SCHEMA,
)
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

    @swagger_auto_schema(**WHATSAPP_WEBHOOK_VERIFY_SCHEMA)
    def get(self, request):
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse("Verification failed", status=403)

    @swagger_auto_schema(**WHATSAPP_WEBHOOK_POST_SCHEMA)
    def post(self, request):
        WebhookHandler().process_webhook(request.data, request=request)
        return Response({"status": "received"}, status=status.HTTP_200_OK)


# ─── Reply endpoints ───────────────────────────────────────────────────────────


class ReplyDirectView(APIView):
    permission_classes = []
    parser_classes = BOT_PARSERS

    @swagger_auto_schema(**REPLY_DIRECT_SCHEMA)
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

    @swagger_auto_schema(**REPLY_MAX_SCHEMA)
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

    @swagger_auto_schema(**REPLY_RESULTS_SCHEMA)
    def post(self, request):
        serializer = ReplyResultsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        to = serializer.validated_data["to"]
        result_type = serializer.validated_data["result_type"]
        data = serializer.validated_data["data"]

        if result_type == "flights":
            chunks = ResultsFormatter.format_flights(data)
        elif result_type == "hotel_rates":
            chunks = ResultsFormatter.format_hotel_rates(data)
        else:
            chunks = ResultsFormatter.format_hotels(data)

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

    @swagger_auto_schema(**MEDIA_PROXY_SCHEMA)
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
