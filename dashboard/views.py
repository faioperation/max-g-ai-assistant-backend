from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from whatsapp.models import WhatsAppContact, WhatsAppMessage
from dashboard.serializers import ContactListSerializer, SendMessageSerializer
from whatsapp.serializers import WhatsAppMessageSerializer
from whatsapp.services.meta_api import MetaAPI
from django.core.files.storage import default_storage
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import os


class ContactListView(generics.ListAPIView):
    queryset = WhatsAppContact.objects.all().order_by("-last_interaction")
    serializer_class = ContactListSerializer

    @swagger_auto_schema(
        operation_summary="List all WhatsApp contacts",
        operation_description=(
            "Returns all contacts sorted by their most recent interaction (newest first). "
            "Each contact includes their last message body and timestamp for quick reference."
        ),
        tags=["Dashboard"],
        responses={200: ContactListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class MessageHistoryView(generics.ListAPIView):
    serializer_class = WhatsAppMessageSerializer

    def get_queryset(self):
        contact_id = self.kwargs.get("id")
        return WhatsAppMessage.objects.filter(contact_id=contact_id).order_by("timestamp")

    @swagger_auto_schema(
        operation_summary="Get full chat history for a contact",
        operation_description=(
            "Returns all messages (both incoming and outgoing) for a given contact, "
            "sorted chronologically (oldest first). "
            "Useful for rendering a full conversation view."
        ),
        tags=["Dashboard"],
        manual_parameters=[
            openapi.Parameter(
                "id", openapi.IN_PATH,
                type=openapi.TYPE_INTEGER,
                description="Contact ID from the contacts list",
            )
        ],
        responses={200: WhatsAppMessageSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SendManualMessageView(APIView):

    @swagger_auto_schema(
        operation_summary="Send a message manually (dashboard)",
        operation_description=(
            "Allows the dashboard operator to manually send a WhatsApp message to any contact.\n\n"
            "Supports three modes:\n"
            "- **Text**: set `message_type=text` and provide `body`\n"
            "- **Media via URL**: set `message_type` and `media_url` (publicly accessible link)\n"
            "- **File upload**: set `message_type` and attach `file` (uploaded to Meta first)\n\n"
            "The sent message is saved to the database automatically.\n\n"
            "### Example Request Payload\n"
            "```json\n"
            "{\n"
            '  "phone_number": "8801641697469",\n'
            '  "message_type": "text",\n'
            '  "body": "Hello from the dashboard admin!"\n'
            "}\n"
            "```\n\n"
            "### Example Response Payload\n"
            "```json\n"
            "{\n"
            '  "messaging_product": "whatsapp",\n'
            '  "contacts": [{ "input": "8801641697469", "wa_id": "8801641697469" }],\n'
            '  "messages": [{ "id": "wamid.HBg..." }]\n'
            "}\n"
            "```"
        ),
        tags=["Dashboard"],
        request_body=SendMessageSerializer,
        responses={
            200: openapi.Response("Message sent successfully — Meta API response"),
            400: openapi.Response("Validation error"),
            502: openapi.Response("Meta API error"),
        },
    )
    def post(self, request):
        serializer = SendMessageSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data["phone_number"]
            msg_type = serializer.validated_data["message_type"]
            body = serializer.validated_data.get("body", "")
            media_url = serializer.validated_data.get("media_url")
            file = serializer.validated_data.get("file")

            meta_api = MetaAPI()

            contact, _ = WhatsAppContact.objects.get_or_create(
                phone_number=phone_number
            )

            response = {}
            if msg_type == "text":
                response = meta_api.send_text_message(phone_number, body)
            else:
                if file:
                    file_name = default_storage.save(f"temp/{file.name}", file)
                    file_path = default_storage.path(file_name)
                    try:
                        upload_res = meta_api.upload_media(file_path, file.content_type)
                        media_id = upload_res.get("id")
                        if media_id:
                            response = meta_api.send_media_message(
                                phone_number, msg_type, media_id=media_id
                            )
                        else:
                            return Response(
                                {"error": "Failed to upload to Meta", "detail": upload_res},
                                status=status.HTTP_502_BAD_GATEWAY,
                            )
                    finally:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                elif media_url:
                    response = meta_api.send_media_message(
                        phone_number, msg_type, media_url=media_url
                    )
                else:
                    return Response(
                        {"error": "Either file or media_url must be provided for media messages"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            if "messages" in response:
                WhatsAppMessage.objects.create(
                    contact=contact,
                    direction="out",
                    message_type=msg_type,
                    body=body,
                    media_url=media_url,
                    wa_message_id=response["messages"][0]["id"],
                    status="sent",
                )
                return Response(response, status=status.HTTP_200_OK)

            return Response(response, status=status.HTTP_502_BAD_GATEWAY)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
