import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from stays.serializers import StaySearchSerializer, StayHoldSerializer
from stays.schemas import (
    STAY_SEARCH_SCHEMA,
    STAY_RATES_SCHEMA,
    STAY_HOLD_SCHEMA,
    STAY_PAYMENT_CHECKOUT_SCHEMA,
    STAY_PAYMENT_SUCCESS_SCHEMA,
)
from stays.services.duffel_stays import (
    geocode_location,
    search_stays,
    get_stay_rates,
    create_stay_quote,
    book_stay,
    create_payment_intent,
    get_payment_intent,
)
from stays.models import PendingStayBooking
from django.shortcuts import render
import json


logger = logging.getLogger(__name__)


class StaySearchView(APIView):

    @swagger_auto_schema(**STAY_SEARCH_SCHEMA)
    def post(self, request):
        serializer = StaySearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        v_data = serializer.validated_data
        location_name = v_data.get("location_name")
        radius = v_data.get("radius", 5)
        check_in = v_data.get("check_in_date").isoformat()
        check_out = v_data.get("check_out_date").isoformat()
        guests = v_data.get("guests")
        rooms = v_data.get("rooms", 1)

        #  Geocode
        lat, lng = geocode_location(location_name)
        if lat is None or lng is None:
            return Response(
                {"error": f"Could not find coordinates for location: {location_name}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Search Duffel
        data, error = search_stays(lat, lng, check_in, check_out, guests, rooms, radius)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_200_OK)


class StayRatesView(APIView):

    @swagger_auto_schema(**STAY_RATES_SCHEMA)
    def post(self, request):
        search_result_id = request.data.get(
            "search_result_id"
        ) or request.query_params.get("search_result_id")
        if not search_result_id:
            return Response(
                {
                    "error": "search_result_id is required (pass as query param or JSON body)"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data, error = get_stay_rates(search_result_id)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_200_OK)


class StayHoldView(APIView):
    permission_classes = []

    @swagger_auto_schema(**STAY_HOLD_SCHEMA)
    def post(self, request):
        serializer = StayHoldSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        v_data = serializer.validated_data
        rate_id = v_data["rate_id"]
        guests = v_data["guests"]
        phone_number = v_data["phone_number"]
        email = v_data["email"]
        whatsapp_number = v_data["whatsapp_number"]

        quote, error = create_stay_quote(rate_id)
        if error:
            return Response(
                {"error": f"Failed to create quote: {error}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = quote["total_amount"]
        currency = quote["total_currency"]

        # payment
        intent, err = create_payment_intent(amount, currency)
        if err:
            return Response(
                {"error": f"Failed to create payment intent: {err}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        PendingStayBooking.objects.create(
            quote_id=quote["quote_id"],
            payment_intent_id=intent["id"],
            client_token=intent["client_token"],
            whatsapp_number=whatsapp_number,
            raw_booking_data={
                "guests": guests,
                "phone_number": phone_number,
                "email": email,
            },
            status="pending",
        )

        checkout_url = request.build_absolute_uri(
            f"/api/v1/stays/checkout/{intent['id']}/"
        )

        return Response(
            {
                "checkout_url": checkout_url,
                "quote_id": quote["quote_id"],
                "amount": amount,
                "currency": currency,
            },
            status=status.HTTP_200_OK,
        )


class StayPaymentCheckoutView(APIView):
    permission_classes = []

    @swagger_auto_schema(**STAY_PAYMENT_CHECKOUT_SCHEMA)
    def get(self, request, intent_id):
        try:
            booking = PendingStayBooking.objects.get(payment_intent_id=intent_id)
        except PendingStayBooking.DoesNotExist:
            return Response(
                {"error": "Invalid payment link"}, status=status.HTTP_404_NOT_FOUND
            )

        if booking.status == "paid":
            return Response(
                {"message": "This order has already been paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client_token = booking.client_token
        if not client_token:
            intent_data, err = get_payment_intent(intent_id)
            if err:
                return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)
            client_token = intent_data.get("client_token")

        if not client_token:
            return Response(
                {"error": "Payment token not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return render(
            request,
            "stays/checkout.html",
            {"client_token": client_token, "intent_id": intent_id},
        )


class StayPaymentSuccessAPIView(APIView):
    permission_classes = []

    @swagger_auto_schema(**STAY_PAYMENT_SUCCESS_SCHEMA)
    def post(self, request):
        intent_id = request.data.get("intent_id")
        if not intent_id:
            return Response(
                {"error": "Missing intent_id"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            booking = PendingStayBooking.objects.get(
                payment_intent_id=intent_id, status="pending"
            )
        except PendingStayBooking.DoesNotExist:
            return Response(
                {"error": "Booking not found or already paid."},
                status=status.HTTP_404_NOT_FOUND,
            )

        intent_data, err = get_payment_intent(intent_id)
        if err or intent_data.get("status") != "succeeded":
            return Response(
                {"error": "Payment not completed or verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Confirm the booking via Duffel Stays
        raw_data = booking.raw_booking_data
        booking_res, booking_err = book_stay(
            quote_id=booking.quote_id,
            guests=raw_data["guests"],
            phone_number=raw_data["phone_number"],
            email=raw_data["email"],
        )

        if booking_err:
            booking.status = "failed"
            booking.save()
            return Response(
                {"error": f"Failed to confirm booking: {booking_err}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = "paid"
        booking.duffel_booking_id = booking_res.get("id")
        booking.save()

        # Send confirmation via WhatsApp
        try:
            from whatsapp.services.meta_api import MetaAPI
            from django.conf import settings

            meta_api = MetaAPI()
            user_msg = f"🎉 Your payment for Hotel Stay '{booking.duffel_booking_id}' was successful! Your booking is confirmed."

            # Additional booking details link if available
            dashboard_url = f"https://app.duffel.com/25aa8ec5a53032c948afa12/test/stays/bookings/{booking.duffel_booking_id}"
            user_msg += f"\n\nYou can view your booking here: {dashboard_url}"

            meta_api.send_text_message(booking.whatsapp_number, user_msg)

            admin_number = getattr(settings, "WHATSAPP_ADMIN_NUMBER", None)
            if admin_number:
                admin_msg = f"🔔 *Stay Payment Received*\n\nUser: {booking.whatsapp_number}\nAmount: {intent_data['amount']} {intent_data['currency']}\nBooking ID: {booking.duffel_booking_id}\nDashboard: {dashboard_url}"
                meta_api.send_text_message(admin_number, admin_msg)
        except Exception as e:
            logger.error(f"Failed to send success WhatsApp for stay: {str(e)}")

        return Response(
            {
                "status": "success",
                "booking_id": booking.duffel_booking_id,
                "dashboard_url": dashboard_url if "dashboard_url" in locals() else None,
            },
            status=status.HTTP_200_OK,
        )
