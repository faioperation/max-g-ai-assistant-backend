from django.contrib import admin
from .models import WhatsAppContact, WhatsAppMessage, PendingBooking

@admin.register(WhatsAppContact)
class WhatsAppContactAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "profile_name", "last_interaction", "created_at")
    search_fields = ("phone_number", "profile_name")

@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ("contact", "direction", "message_type", "status", "timestamp")
    list_filter = ("direction", "message_type", "status")
    search_fields = ("contact__phone_number", "body")

@admin.register(PendingBooking)
class PendingBookingAdmin(admin.ModelAdmin):
    list_display = ("contact", "offer_id", "is_paid", "created_at")
    list_filter = ("is_paid",)
