from django.db import models

class WhatsAppContact(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    profile_name = models.CharField(max_length=255, blank=True, null=True)
    profile_pic_url = models.URLField(blank=True, null=True)
    last_interaction = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile_name or 'Unknown'} ({self.phone_number})"

    class Meta:
        verbose_name = "WhatsApp Contact"
        verbose_name_plural = "WhatsApp Contacts"

class WhatsAppMessage(models.Model):
    DIRECTION_CHOICES = [
        ("in", "Incoming"),
        ("out", "Outgoing"),
    ]
    MESSAGE_TYPE_CHOICES = [
        ("text", "Text"),
        ("image", "Image"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("document", "Document"),
        ("sticker", "Sticker"),
        ("location", "Location"),
        ("reaction", "Reaction"),
    ]
    STATUS_CHOICES = [
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
        ("failed", "Failed"),
    ]

    contact = models.ForeignKey(WhatsAppContact, on_delete=models.CASCADE, related_name="messages")
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default="text")
    body = models.TextField(blank=True, null=True)
    media_id = models.CharField(max_length=255, blank=True, null=True)
    media_url = models.URLField(blank=True, null=True)
    media_mime_type = models.CharField(max_length=100, blank=True, null=True)
    wa_message_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="sent")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.direction} - {self.message_type} - {self.contact.phone_number}"

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "WhatsApp Message"
        verbose_name_plural = "WhatsApp Messages"

class PendingBooking(models.Model):
    contact = models.ForeignKey(WhatsAppContact, on_delete=models.CASCADE, related_name="bookings")
    offer_id = models.CharField(max_length=255)
    passenger_data = models.JSONField()
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking for {self.contact.phone_number} - {self.offer_id}"

    class Meta:
        verbose_name = "Pending Booking"
        verbose_name_plural = "Pending Bookings"
