from rest_framework import serializers
from whatsapp.models import WhatsAppContact, WhatsAppMessage
from whatsapp.serializers import WhatsAppMessageSerializer

class ContactListSerializer(serializers.ModelSerializer):
    last_message_body = serializers.SerializerMethodField()
    last_message_timestamp = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppContact
        fields = ["id", "phone_number", "profile_name", "profile_pic_url", "last_interaction", "last_message_body", "last_message_timestamp"]

    def get_last_message_body(self, obj):
        last_msg = obj.messages.first()
        return last_msg.body if last_msg else None

    def get_last_message_timestamp(self, obj):
        last_msg = obj.messages.first()
        return last_msg.timestamp if last_msg else None

class SendMessageSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    message_type = serializers.ChoiceField(choices=["text", "image", "video", "audio", "document"])
    body = serializers.CharField(required=False, allow_blank=True)
    media_url = serializers.URLField(required=False, allow_blank=True)
    file = serializers.FileField(required=False, allow_null=True)
