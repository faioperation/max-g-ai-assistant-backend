from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def _verify_duffel_signature(request):
    """
    Verifies the Duffel webhook signature from X-Duffel-Signature header.
    Duffel uses a format like: t=timestamp,v2=signature
    We must construct the signed payload as 'timestamp.body' and hash it.
    """
    secret = getattr(settings, "DUFFEL_WEBHOOK_SECRET", None)
    if not secret:
        # If no secret configured, skip verification (dev/testing mode)
        logger.warning("DUFFEL_WEBHOOK_SECRET not set. Skipping signature verification.")
        return True

    signature_header = request.headers.get("X-Duffel-Signature", "")
    if not signature_header:
        logger.error("Missing X-Duffel-Signature header from Duffel webhook.")
        return False

    try:
        # 1. Parse the header parts (e.g., t=123,v2=abc)
        parts = {}
        for item in signature_header.split(","):
            if "=" in item:
                k, v = item.split("=", 1)
                parts[k.strip()] = v.strip()
        
        timestamp = parts.get("t")
        received_sig = parts.get("v2") or parts.get("v1")

        if not timestamp or not received_sig:
            # Fallback for old simple signature format if still used by some events
            secret_bytes = secret.encode("utf-8")
            body_bytes = request.body
            expected_signature = hmac.new(secret_bytes, body_bytes, hashlib.sha256).hexdigest()
            is_valid = hmac.compare_digest(expected_signature, signature_header)
            if not is_valid:
                logger.error(f"Legacy signature mismatch. Received: {signature_header}")
            return is_valid

        # 2. Construct the signed payload: timestamp + "." + body
        body_bytes = request.body
        signed_payload = timestamp.encode("utf-8") + b"." + body_bytes
        secret_bytes = secret.encode("utf-8")
        
        # 3. Compute the HMAC-SHA256 signature
        expected_signature = hmac.new(secret_bytes, signed_payload, hashlib.sha256).hexdigest()
        
        # 4. Securely compare signatures
        is_valid = hmac.compare_digest(expected_signature, received_sig)
        if not is_valid:
            logger.error(f"Signature mismatch. Expected: {expected_signature}, Received: {received_sig}")
        return is_valid
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


class DuffelUnifiedWebhookView(APIView):
    """
    Unified webhook handler for all Duffel events (Flights & Stays).
    A single URL registered in the Duffel Dashboard handles both
    flight and stay payment confirmations automatically.

    Security: All incoming requests are verified against DUFFEL_WEBHOOK_SECRET
    to ensure they genuinely come from Duffel, blocking fake/malicious requests.
    """
    permission_classes = []

    def post(self, request):
        # --- SECURITY: Verify the request is genuinely from Duffel ---
        if not _verify_duffel_signature(request):
            logger.warning("Duffel webhook received with invalid signature. Request rejected.")
            return Response({"error": "Invalid signature"}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data
        event_type = payload.get("type")
        data = payload.get("data", {})

        logger.info(f"Received Duffel unified webhook: {event_type}")

        # Events that signal a successful payment
        payment_events = [
            "payment_intent.succeeded",
            "air.payment.succeeded",
            "payment.created",
        ]

        if event_type in payment_events:
            intent_id = data.get("id")

            # 1. Check Flight Bookings first
            try:
                from travel.models import PendingBooking
                from travel.services.duffel import book_flight, pay_held_order, get_order_details
                booking = PendingBooking.objects.filter(
                    payment_intent_id=intent_id, status="pending"
                ).first()
                if booking:
                    logger.info(f"Flight payment {intent_id} detected via webhook. Triggering booking.")
                    return self._confirm_flight_booking(booking, intent_id)
            except Exception as e:
                logger.error(f"Webhook flight booking error: {e}")

            # 2. Check Stay Bookings
            try:
                from stays.models import PendingStayBooking
                from stays.services.duffel_stays import book_stay
                stay_booking = PendingStayBooking.objects.filter(
                    payment_intent_id=intent_id, status="pending"
                ).first()
                if stay_booking:
                    logger.info(f"Stay payment {intent_id} detected via webhook. Triggering booking.")
                    return self._confirm_stay_booking(stay_booking)
            except Exception as e:
                logger.error(f"Webhook stay booking error: {e}")

            return Response({"status": "ignored — no pending booking matched"}, status=status.HTTP_200_OK)

        # Handle Duffel Stays booking created event
        if event_type == "stays.booking.created":
            duffel_booking_id = data.get("id")
            return self._handle_stay_booking_confirmed(duffel_booking_id)

        return Response({"status": "received"}, status=status.HTTP_200_OK)

    def _confirm_flight_booking(self, booking, intent_id):
        """
        Book the flight atomically using the Payment Intent ID.
        If it's a held order, pay via Duffel balance instead.
        """
        from travel.services.duffel import book_flight, pay_held_order, get_order_details

        try:
            if booking.duffel_order_id:
                # Held order — pay via balance
                raw_booking, pay_err = pay_held_order(
                    booking.duffel_order_id,
                    booking.raw_booking_data.get("amount"),
                    booking.raw_booking_data.get("currency"),
                )
            else:
                # Instant order — book using balance
                raw = booking.raw_booking_data or {}
                raw_booking, pay_err = book_flight(
                    offer_id=raw["offer_id"],
                    passengers_input=raw["passengers"],
                    payment_type="balance",
                    order_type="instant"
                )
                if not pay_err:
                    booking.duffel_order_id = raw_booking["order_id"]

            if pay_err:
                booking.status = "failed"
                booking.save()
                logger.error(f"Webhook flight booking failed for intent {intent_id}: {pay_err}")
                return Response({"status": "booking_failed", "error": str(pay_err)}, status=status.HTTP_200_OK)

            booking.status = "paid"
            booking.save()
            logger.info(f"Webhook: Flight booking confirmed. Order: {booking.duffel_order_id}")

            # Send WhatsApp notification
            self._notify_flight_success(booking)

        except Exception as e:
            logger.error(f"Webhook _confirm_flight_booking exception: {e}")

        return Response({"status": "flight booking confirmed"}, status=status.HTTP_200_OK)

    def _confirm_stay_booking(self, stay_booking):
        """Confirm a pending stay booking after payment succeeds via webhook."""
        from stays.services.duffel_stays import book_stay

        try:
            raw_data = stay_booking.raw_booking_data
            booking_res, booking_err = book_stay(
                quote_id=stay_booking.quote_id,
                guests=raw_data["guests"],
                phone_number=raw_data["phone_number"],
                email=raw_data["email"],
            )

            if booking_err:
                stay_booking.status = "failed"
                stay_booking.save()
                logger.error(f"Webhook stay booking failed: {booking_err}")
                return Response({"status": "stay_booking_failed"}, status=status.HTTP_200_OK)

            stay_booking.status = "paid"
            stay_booking.duffel_booking_id = booking_res.get("id")
            stay_booking.save()
            logger.info(f"Webhook: Stay booking confirmed. ID: {stay_booking.duffel_booking_id}")

        except Exception as e:
            logger.error(f"Webhook _confirm_stay_booking exception: {e}")

        return Response({"status": "stay booking confirmed"}, status=status.HTTP_200_OK)

    def _handle_stay_booking_confirmed(self, duffel_booking_id):
        """Handle stays.booking.created event — mark the pending stay booking as paid."""
        try:
            from stays.models import PendingStayBooking
            booking = PendingStayBooking.objects.filter(
                duffel_booking_id=duffel_booking_id, status="pending"
            ).first()
            if booking:
                booking.status = "paid"
                booking.save()
                logger.info(f"Stay booking {duffel_booking_id} confirmed via stays.booking.created event.")
                return Response({"status": "stay booking confirmed"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error handling stays.booking.created: {e}")
        return Response({"status": "ignored stay event"}, status=status.HTTP_200_OK)

    def _notify_flight_success(self, booking):
        """Send WhatsApp notification after successful flight booking."""
        try:
            from travel.services.duffel import get_order_details
            from whatsapp.services.meta_api import MetaAPI
            from django.conf import settings

            order_data, _ = get_order_details(booking.duffel_order_id)
            pdf_url = None
            if order_data and "documents" in order_data:
                for doc in order_data["documents"]:
                    if doc.get("type") == "electronic_ticket":
                        pdf_url = doc.get("pdf_url")
                        break

            dashboard_url = f"https://app.duffel.com/25aa8ec5a53032c948afa12/test/orders/{booking.duffel_order_id}"
            meta_api = MetaAPI()

            user_msg = f"🎉 Your payment was successful! Flight order #{booking.duffel_order_id} is confirmed."
            user_msg += f"\n\n{'📥 Download ticket: ' + pdf_url if pdf_url else '📄 View booking: ' + dashboard_url}"
            meta_api.send_text_message(booking.whatsapp_number, user_msg)

            admin_number = getattr(settings, "WHATSAPP_ADMIN_NUMBER", None)
            if admin_number:
                admin_msg = f"🔔 *Flight Payment*\n\nUser: {booking.whatsapp_number}\nOrder: {booking.duffel_order_id}\nTicket: {pdf_url or dashboard_url}"
                meta_api.send_text_message(admin_number, admin_msg)
        except Exception as e:
            logger.error(f"Webhook WhatsApp notify failed: {e}")
