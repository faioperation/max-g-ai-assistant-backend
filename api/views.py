from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

class DuffelUnifiedWebhookView(APIView):
    """
    Unified webhook handler for all Duffel events (Flights & Stays).
    Points to a single URL in Duffel Dashboard for easier management.
    """
    permission_classes = []

    def post(self, request):
        payload = request.data
        event_type = payload.get("type")
        data = payload.get("data", {})
        
        logger.info(f"Received Duffel unified webhook: {event_type}")

        # Map different payment success events to our confirmation logic
        payment_events = [
            "payment_intent.succeeded", 
            "air.payment.succeeded", 
            "payment.created",
            "stays.booking.created" # Adding this as a fallback for stays
        ]

        if event_type in payment_events:
            # For stays.booking.created, the id might be the booking id, 
            # but we usually need the intent_id or we match by duffel_booking_id.
            # However, for consistency, we'll try to find the intent_id first.
            intent_id = data.get("id")
            
            if not intent_id and event_type == "stays.booking.created":
                # If it's a stay booking created event, we might match by booking id instead
                booking_id = data.get("id")
                return self._handle_stay_booking_by_id(booking_id)

            # 1. Search in Flight Bookings
            try:
                from travel.models import PendingBooking
                from travel.views import PaymentSuccessAPIView
                booking = PendingBooking.objects.filter(payment_intent_id=intent_id, status="pending").first()
                if booking:
                    logger.info(f"Flight payment/event {intent_id} detected. Triggering confirmation.")
                    return self._trigger_success(PaymentSuccessAPIView, intent_id)
            except ImportError:
                pass

            # 2. Search in Stay Bookings
            try:
                from stays.models import PendingStayBooking
                from stays.views import StayPaymentSuccessAPIView
                stay_booking = PendingStayBooking.objects.filter(payment_intent_id=intent_id, status="pending").first()
                if stay_booking:
                    logger.info(f"Stay payment/event {intent_id} detected. Triggering confirmation.")
                    return self._trigger_success(StayPaymentSuccessAPIView, intent_id)
            except ImportError:
                pass
            
            return Response({"status": "ignored (no pending booking match for ID)"}, status=status.HTTP_200_OK)

        return Response({"status": "received"}, status=status.HTTP_200_OK)

    def _handle_stay_booking_by_id(self, booking_id):
        # Fallback helper for stay booking events
        from stays.models import PendingStayBooking
        booking = PendingStayBooking.objects.filter(duffel_booking_id=booking_id).first()
        if booking and booking.status == "pending":
            booking.status = "paid"
            booking.save()
            return Response({"status": "stay booking marked as paid via booking_id"}, status=status.HTTP_200_OK)
        return Response({"status": "ignored stay event"}, status=status.HTTP_200_OK)

    def _trigger_success(self, view_class, intent_id):
        from django.test import RequestFactory
        factory = RequestFactory()
        # Simulate the frontend API call that would happen on the success page
        sim_request = factory.post('/api/dummy/', {'intent_id': intent_id}, content_type='application/json')
        view = view_class.as_view()
        return view(sim_request)
