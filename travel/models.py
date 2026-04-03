from django.db import models


class PendingBooking(models.Model):
    duffel_order_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True
    )
    payment_intent_id = models.CharField(max_length=255, unique=True)
    client_token = models.TextField(null=True, blank=True)
    whatsapp_number = models.CharField(max_length=20)
    raw_booking_data = models.JSONField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed")],
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.whatsapp_number} - {self.duffel_order_id or 'Deferred'} ({self.status})"
