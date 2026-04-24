from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from whatsapp.serializers import (
    ReplyDirectSerializer,
    ReplyMaxSerializer,
    ReplyResultsSerializer,
    ReplyResponseSerializer,
)

WHATSAPP_WEBHOOK_VERIFY_SCHEMA = {
    "operation_summary": "Meta Webhook Verification",
    "operation_description": (
        "Used by Meta to verify ownership of the webhook endpoint. "
        "Returns the hub.challenge value if the verify_token matches."
    ),
    "tags": ["WhatsApp Webhook"],
    "manual_parameters": [
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
    "responses": {
        200: openapi.Response("Returns hub.challenge"),
        403: openapi.Response("Invalid token"),
    },
}

WHATSAPP_WEBHOOK_POST_SCHEMA = {
    "operation_summary": "Receive incoming WhatsApp messages",
    "operation_description": (
        "Meta posts all incoming events here. "
        "Saves the message to DB and forwards it to the AI bot.\n\n"
        "**Must return 200 within 5 s or Meta will retry.**"
    ),
    "tags": ["WhatsApp Webhook"],
    "request_body": openapi.Schema(
        type=openapi.TYPE_OBJECT, description="Standard Meta Webhook payload"
    ),
    "responses": {200: openapi.Response("Acknowledged")},
}

REPLY_DIRECT_SCHEMA = {
    "operation_summary": "Send reply to a WhatsApp user",
    "operation_description": (
        "Called by the AI agent to send a message to a WhatsApp user.\n\n"
        "**Message types:** `text` (requires `body`) | `image/video/audio/document` (requires `media_url`)\n\n"
        "### Example Request\n"
        "```json\n"
        '{ "to": "8801641697469", "message_type": "text", "body": "Your flight is confirmed!" }\n'
        "```\n\n"
        "### Example Response\n"
        '```json\n{ "status": "sent", "wa_message_id": "wamid.HBg...", "to": "8801641697469" }\n```'
    ),
    "tags": ["WhatsApp Reply"],
    "request_body": ReplyDirectSerializer,
    "responses": {
        200: ReplyResponseSerializer,
        400: openapi.Response("Validation error"),
        502: openapi.Response("Meta API error"),
    },
}

REPLY_MAX_SCHEMA = {
    "operation_summary": "Send notification to Max (admin)",
    "operation_description": (
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
    "tags": ["WhatsApp Reply"],
    "request_body": ReplyMaxSerializer,
    "responses": {
        200: ReplyResponseSerializer,
        400: openapi.Response("Validation error"),
        503: openapi.Response("Admin number not set"),
        502: openapi.Response("Meta API error"),
    },
}

REPLY_RESULTS_SCHEMA = {
    "operation_summary": "Send formatted search results to user",
    "operation_description": (
        "Takes a JSON list of flight offers or hotel search results, formats them as text, "
        "and sends them to the WhatsApp user. "
        "Large lists are automatically split into multiple messages.\n\n"
        "### Example Request\n"
        "```json\n"
        "{\n"
        '  "to": "8801641697469",\n'
        '  "result_type": "flights",\n'
        '  "data": [... JSON from search ...]\n'
        "}\n"
        "```"
    ),
    "tags": ["WhatsApp Reply"],
    "request_body": ReplyResultsSerializer,
    "responses": {
        200: openapi.Response("Results sent successfully"),
        400: openapi.Response("Validation error"),
    },
}

MEDIA_PROXY_SCHEMA = {
    "operation_summary": "Stream Meta media file",
    "operation_description": (
        "Proxies a media file from Meta's CDN. "
        "Avoids exposing the Meta access token to clients."
    ),
    "tags": ["WhatsApp Media"],
    "manual_parameters": [
        openapi.Parameter(
            "media_id",
            openapi.IN_PATH,
            type=openapi.TYPE_STRING,
            description="Meta media ID",
        ),
    ],
    "responses": {
        200: openapi.Response("Raw file binary"),
        404: openapi.Response("Not found"),
        502: openapi.Response("CDN fetch failed"),
    },
}
