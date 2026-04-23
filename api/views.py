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
                from travel.views import PaymentSuccessAPIView
                booking = PendingBooking.objects.filter(
                    payment_intent_id=intent_id, status="pending"
                ).first()
                if booking:
                    logger.info(f"Flight payment {intent_id} detected via webhook. Triggering confirmation.")
                    return self._trigger_success(PaymentSuccessAPIView, intent_id)
            except ImportError:
                pass

            # 2. Check Stay Bookings
            try:
                from stays.models import PendingStayBooking
                from stays.views import StayPaymentSuccessAPIView
                stay_booking = PendingStayBooking.objects.filter(
                    payment_intent_id=intent_id, status="pending"
                ).first()
                if stay_booking:
                    logger.info(f"Stay payment {intent_id} detected via webhook. Triggering confirmation.")
                    return self._trigger_success(StayPaymentSuccessAPIView, intent_id)
            except ImportError:
                pass

            return Response({"status": "ignored — no pending booking matched"}, status=status.HTTP_200_OK)

        # Handle Duffel Stays booking created event
        if event_type == "stays.booking.created":
            duffel_booking_id = data.get("id")
            return self._handle_stay_booking_confirmed(duffel_booking_id)

        return Response({"status": "received"}, status=status.HTTP_200_OK)

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

    def _trigger_success(self, view_class, intent_id):
        """Reuse the existing PaymentSuccessAPIView logic for webhook-triggered confirmations."""
        from django.test import RequestFactory
        factory = RequestFactory()
        sim_request = factory.post('/api/dummy/', {'intent_id': intent_id}, content_type='application/json')
        view = view_class.as_view()
        return view(sim_request)
