from django.db import models

class PendingStayBooking(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending Payment"),
        ("paid", "Paid & Confirmed"),
        ("failed", "Failed"),
    )

    quote_id = models.CharField(max_length=255, help_text="Duffel Stays Quote ID")
    duffel_booking_id = models.CharField(max_length=255, blank=True, null=True, help_text="Duffel Stays Booking ID (Confirmed)")
    payment_intent_id = models.CharField(max_length=255, help_text="Duffel Payment Intent ID")
    client_token = models.CharField(max_length=1000, help_text="Token for Duffel UI Component")
    whatsapp_number = models.CharField(max_length=50)
    raw_booking_data = models.JSONField(help_text="Stores guests, email, phone number, etc required for final booking")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"StayBooking {self.quote_id} - {self.status}"
