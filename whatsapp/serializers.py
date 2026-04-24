from rest_framework import serializers
from whatsapp.models import WhatsAppContact, WhatsAppMessage, PendingBooking


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppMessage
        fields = "__all__"


class WhatsAppContactSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppContact
        fields = [
            "id",
            "phone_number",
            "profile_name",
            "profile_pic_url",
            "last_interaction",
            "created_at",
            "last_message",
        ]

    def get_last_message(self, obj):
        last_msg = obj.messages.first()
        if last_msg:
            return WhatsAppMessageSerializer(last_msg).data
        return None


class PendingBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PendingBooking
        fields = "__all__"


class ReplyDirectSerializer(serializers.Serializer):
    to = serializers.CharField(
        max_length=20,
        help_text="Recipient WhatsApp number in E.164 format (e.g. 8801641697469)",
    )
    message_type = serializers.ChoiceField(
        choices=["text", "image", "video", "audio", "document"],
        help_text="Type of message to send",
    )
    body = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Text body (required for message_type=text)",
    )
    media_url = serializers.URLField(
        required=False,
        allow_null=True,
        help_text="Publicly accessible URL for media messages",
    )
    caption = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional caption for media messages",
    )


class ReplyMaxSerializer(serializers.Serializer):
    message_type = serializers.ChoiceField(
        choices=["text", "image", "video", "audio", "document"],
        help_text="Type of message to send to the admin (Max)",
    )
    body = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Text body (required for message_type=text)",
    )
    media_url = serializers.URLField(
        required=False,
        allow_null=True,
        help_text="Publicly accessible URL for media messages",
    )
    caption = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional caption for media messages",
    )


class ReplyResultsSerializer(serializers.Serializer):
    to = serializers.CharField(
        max_length=20,
        help_text="Recipient WhatsApp number in E.164 format",
    )
    result_type = serializers.ChoiceField(
        choices=["flights", "hotels"],
        help_text="Type of results being sent (affects formatting)",
    )
    data = serializers.JSONField(
        help_text="The JSON list of flight offers or hotel search results"
    )
    chunk_size = serializers.IntegerField(
        default=5,
        min_value=1,
        max_value=10,
        help_text="Number of results per WhatsApp message",
    )


class ReplyResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    wa_message_id = serializers.CharField(allow_null=True)
    to = serializers.CharField()
