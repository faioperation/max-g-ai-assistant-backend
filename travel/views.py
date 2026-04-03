import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from django.shortcuts import render
from rest_framework.views import APIView

from travel.models import PendingBooking
from travel.schema_examples import *
from travel.serializers import (
    FlightBookSerializer,
    FlightSearchSerializer,
    FlightHoldSerializer,
)
from travel.services.duffel import (
    book_flight,
    get_headers,
    search_flights,
    create_payment_intent,
    get_payment_intent,
    pay_held_order,
    get_offer,
    get_order_details,
)

logger = logging.getLogger(__name__)


class FlightSearchView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Search for available flights",
        operation_description=(
            "Search for available flight offers via Duffel API. "
            "Returns a deduplicated list of offers formatted for display.\n\n"
            "Use the returned `offer_id` to call `/flights/book/` or `/flights/hold/`.\n\n"
            "### Example Request\n"
            + SEARCH_EXAMPLE_REQUEST
            + "\n### Example Response\n"
            + SEARCH_EXAMPLE_RESPONSE
        ),
        tags=["Travel — Flights"],
        request_body=FlightSearchSerializer,
        responses={
            200: openapi.Response("List of available offers"),
            400: openapi.Response("Validation or Duffel error"),
            503: openapi.Response("Duffel API not configured"),
        },
    )
    def post(self, request):
        serializer = FlightSearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            get_headers()
        except ValueError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        try:
            result, error = search_flights(
                slices_data=serializer.validated_data["slices"],
                passengers_data=serializer.validated_data["passengers"],
                max_results=serializer.validated_data.get("max_results", 50),
            )
            if error:
                return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FlightBookView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Book a flight offer (Instant Pay)",
        operation_description=(
            "Confirm and book a flight using a Duffel `offer_id` from `/flights/search/`.\n"
            "Uses account balance to pay immediately.\n\n"
            "### Example Request\n"
            + BOOK_EXAMPLE_REQUEST
            + "\n### Example Response\n"
            + BOOK_EXAMPLE_RESPONSE
        ),
        tags=["Travel — Flights"],
        request_body=FlightBookSerializer,
        responses={
            200: openapi.Response("Booking confirmed"),
            400: openapi.Response("Validation or Duffel booking error"),
            503: openapi.Response("Duffel API not configured"),
        },
    )
    def post(self, request):
        serializer = FlightBookSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            get_headers()
        except ValueError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        try:
            result, error = book_flight(
                offer_id=serializer.validated_data["offer_id"],
                passengers_input=serializer.validated_data["passengers"],
                payment_type=serializer.validated_data.get("payment_type", "balance"),
            )
            if error:
                return Response(error, status=status.HTTP_400_BAD_REQUEST)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FlightHoldView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Hold a flight and create payment intent",
        operation_description=(
            "Reserve a flight using a Duffel `offer_id` and generate a Payment Intent for checkout.\n\n"
            "Returns a `checkout_url` which should be sent to the user on WhatsApp.\n\n"
            "### Example Request\n"
            + HOLD_EXAMPLE_REQUEST
            + "\n### Example Response\n"
            + HOLD_EXAMPLE_RESPONSE
        ),
        tags=["Travel — Flights"],
        request_body=FlightHoldSerializer,
        responses={
            200: openapi.Response("Payment checkout link generated"),
            400: openapi.Response("Validation or Duffel API error"),
            503: openapi.Response("Duffel API not configured"),
        },
    )
    def post(self, request):
        serializer = FlightHoldSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            get_headers()
        except ValueError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        try:
            result, error = book_flight(
                offer_id=serializer.validated_data["offer_id"],
                passengers_input=serializer.validated_data["passengers"],
                payment_type="balance",
                order_type="hold",
            )

            is_deferred = False
            if error:

                if isinstance(error, str) and "not supported" in error:
                    offer_data, get_err = get_offer(
                        serializer.validated_data["offer_id"]
                    )
                    if get_err:
                        return Response(
                            {"error": f"Failed to fetch offer: {get_err}"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    amount = offer_data["total_amount"]
                    currency = offer_data["total_currency"]
                    order_id = None
                    is_deferred = True
                else:
                    return Response(
                        {"error": f"Hold failed: {error}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                amount = result["total_amount"]
                currency = result["total_currency"]
                order_id = result["order_id"]

            intent, err = create_payment_intent(amount, currency)
            if err:
                return Response(
                    {"error": f"Step 2 (Create Payment Intent) failed: {err}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            import json

            raw_data = None
            if is_deferred:
                raw_data = json.loads(
                    json.dumps(serializer.validated_data, default=str)
                )

            PendingBooking.objects.create(
                duffel_order_id=order_id,
                payment_intent_id=intent["id"],
                client_token=intent["client_token"],
                whatsapp_number=serializer.validated_data["whatsapp_number"],
                raw_booking_data=raw_data,
                status="pending",
            )

            return Response(
                {
                    "checkout_url": request.build_absolute_uri(
                        f"/api/v1/travel/checkout/{intent['id']}/"
                    ),
                    "order_id": order_id,
                    "amount": amount,
                    "currency": currency,
                    "booking_type": "hold" if not is_deferred else "deferred",
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentCheckoutView(APIView):
    """View to serve the HTML checkout page for Duffel Payments."""

    permission_classes = []

    def get(self, request, intent_id):
        try:
            booking = PendingBooking.objects.get(payment_intent_id=intent_id)
        except PendingBooking.DoesNotExist:
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
                {"error": "Payment token not found. Please create a new booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return render(
            request,
            "travel/checkout.html",
            {"client_token": client_token, "intent_id": intent_id},
        )


class PaymentSuccessAPIView(APIView):
    """API called by the frontend when Duffel payment succeeds."""

    permission_classes = []

    def post(self, request):
        intent_id = request.data.get("intent_id")
        if not intent_id:
            return Response(
                {"error": "Missing intent_id"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            booking = PendingBooking.objects.get(
                payment_intent_id=intent_id, status="pending"
            )
        except PendingBooking.DoesNotExist:
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

        if booking.duffel_order_id:
            pay_result, pay_err = pay_held_order(
                booking.duffel_order_id, intent_data["amount"], intent_data["currency"]
            )
        else:
            pay_result, pay_err = book_flight(
                offer_id=booking.raw_booking_data["offer_id"],
                passengers_input=booking.raw_booking_data["passengers"],
                payment_type="balance",
                order_type="instant",
            )
            if not pay_err:
                booking.duffel_order_id = pay_result["order_id"]

        if pay_err:
            booking.status = "failed"
            booking.save()
            return Response(
                {"error": f"Failed to issue ticket: {pay_err}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = "paid"
        booking.save()

        order_data, _ = get_order_details(booking.duffel_order_id)
        pdf_url = None
        if order_data and "documents" in order_data:
            for doc in order_data["documents"]:
                if doc.get("type") == "electronic_ticket":
                    pdf_url = doc.get("pdf_url")
                    break

        dashboard_url = (
            f"https://app.duffel.com/arus/test/orders/{booking.duffel_order_id}"
        )

        try:
            from whatsapp.services.meta_api import MetaAPI
            from django.conf import settings

            meta_api = MetaAPI()

            user_msg = f"🎉 Your payment for flight order #{booking.duffel_order_id} was successful! Your e-ticket is confirmed."
            if pdf_url:
                user_msg += f"\n\nYou can download your ticket here: {pdf_url}"
            else:
                user_msg += f"\n\nYou can view your booking here: {dashboard_url}"

            meta_api.send_text_message(booking.whatsapp_number, user_msg)

            # Notify Admin
            admin_number = getattr(settings, "WHATSAPP_ADMIN_NUMBER", None)
            if admin_number:
                admin_msg = f"🔔 *Payment Received*\n\nUser: {booking.whatsapp_number}\nAmount: {intent_data['amount']} {intent_data['currency']}\nOrder ID: {booking.duffel_order_id}\n\nTicket PDF: {pdf_url if pdf_url else 'Not available yet'}\nDashboard: {dashboard_url}"
                meta_api.send_text_message(admin_number, admin_msg)

        except Exception as e:
            logger.error(f"Failed to send success WhatsApp: {str(e)}")

        return Response(
            {
                "status": "success",
                "order_id": booking.duffel_order_id,
                "pdf_url": pdf_url,
                "dashboard_url": dashboard_url,
            },
            status=status.HTTP_200_OK,
        )
