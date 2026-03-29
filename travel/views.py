import datetime
import json
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import FlightSearchSerializer, FlightBookSerializer


DUFFEL_API_URL = "https://api.duffel.com/air"

def _duffel_headers():
    token = getattr(settings, "DUFFEL_ACCESS_TOKEN", None)
    if not token:
        raise ValueError("Duffel API not configured — set DUFFEL_ACCESS_TOKEN in .env")
    return {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": "v2",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }


class FlightSearchView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Search for available flights",
        operation_description=(
            "Search for available flight offers using the Duffel API.\n\n"
            "Use the returned `offer_id` from each offer to call `/flights/book/`."
        ),
        tags=["Travel — Flights"],
        request_body=FlightSearchSerializer,
        responses={
            200: openapi.Response(
                "List of available offers",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "offer_request_id": openapi.Schema(type=openapi.TYPE_STRING),
                        "offers_count": openapi.Schema(type=openapi.TYPE_INTEGER),
                        "offers": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(type=openapi.TYPE_OBJECT),
                            description="Each object contains offer_id, total_amount, currency, slices, airlines, etc.",
                        ),
                    },
                ),
            ),
            400: openapi.Response("Validation error or Duffel error"),
            503: openapi.Response("Duffel API not configured"),
        },
    )
    def post(self, request):
        serializer = FlightSearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            headers = _duffel_headers()
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            slices_data = serializer.validated_data["slices"]
            passengers_data = serializer.validated_data["passengers"]
            max_results = serializer.validated_data.get("max_results", 15)

            slices_payload = [
                {
                    "origin": s["origin"],
                    "destination": s["destination"],
                    "departure_date": s["departure_date"].isoformat()
                    if isinstance(s["departure_date"], datetime.date)
                    else s["departure_date"],
                }
                for s in slices_data
            ]

            payload = {
                "data": {
                    "slices": slices_payload,
                    "passengers": passengers_data
                }
            }

            # 1. Create Offer Request
            or_res = requests.post(f"{DUFFEL_API_URL}/offer_requests", headers=headers, json=payload)
            if or_res.status_code >= 400:
                err_data = or_res.json()
                msg = err_data.get("errors", [{"message": "Duffel error"}])[0].get("message")
                return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

            offer_request_id = or_res.json()["data"]["id"]

            # 2. List Offers
            offers_res = requests.get(
                f"{DUFFEL_API_URL}/offers", 
                headers=headers,
                params={"offer_request_id": offer_request_id, "limit": max_results}
            )
            
            if offers_res.status_code >= 400:
                err_data = offers_res.json()
                msg = err_data.get("errors", [{"message": "Duffel error"}])[0].get("message")
                return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

            offers_raw = offers_res.json().get("data", [])

            offers = []
            for raw in offers_raw:
                offers.append({
                    "offer_id": raw.get("id"),
                    "total_amount": raw.get("total_amount"),
                    "total_currency": raw.get("total_currency"),
                    "base_amount": raw.get("base_amount"),
                    "tax_amount": raw.get("tax_amount"),
                    "expires_at": raw.get("expires_at"),
                    "slices": raw.get("slices", []),
                    "passengers": raw.get("passengers", []),
                    "owner": raw.get("owner", {}),  
                })

            return Response(
                {
                    "offer_request_id": offer_request_id,
                    "offers_count": len(offers),
                    "offers": offers,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FlightBookView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Confirm and book a flight offer",
        operation_description=(
            "Books a flight using a Duffel `offer_id` obtained from `/flights/search/`.\n\n"
        ),
        tags=["Travel — Flights"],
        request_body=FlightBookSerializer,
        responses={
            200: openapi.Response(
                "Booking confirmed",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "order_id": openapi.Schema(type=openapi.TYPE_STRING),
                        "booking_reference": openapi.Schema(type=openapi.TYPE_STRING),
                        "status": openapi.Schema(type=openapi.TYPE_STRING),
                        "total_amount": openapi.Schema(type=openapi.TYPE_STRING),
                        "passengers": openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                        "slices": openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                    },
                ),
            ),
            400: openapi.Response("Validation error or Duffel booking error"),
            503: openapi.Response("Duffel API not configured"),
        },
    )
    def post(self, request):
        serializer = FlightBookSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            headers = _duffel_headers()
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            offer_id = serializer.validated_data["offer_id"]
            passengers = serializer.validated_data["passengers"]
            payment_type = serializer.validated_data.get("payment_type", "balance")

            for p in passengers:
                if isinstance(p.get("born_on"), datetime.date):
                    p["born_on"] = p["born_on"].isoformat()

            payload = {
                "data": {
                    "type": "instant",
                    "selected_offers": [offer_id],
                    "passengers": passengers,
                    "payments": [{"type": payment_type, "currency": "USD", "amount": "0.00"}]
                }
            }

            res = requests.post(f"{DUFFEL_API_URL}/orders", headers=headers, json=payload)
            
            if res.status_code >= 400:
                err_data = res.json()
                msg = err_data.get("errors", [{"message": "Duffel booking error"}])[0].get("message")
                return Response({"error": msg, "details": err_data}, status=status.HTTP_400_BAD_REQUEST)

            raw = res.json().get("data", {})

            return Response(
                {
                    "order_id": raw.get("id"),
                    "booking_reference": raw.get("booking_reference"),
                    "status": "awaiting_payment" if raw.get("payment_status", {}).get("awaiting_payment") else "confirmed",
                    "total_amount": raw.get("total_amount"),
                    "total_currency": raw.get("total_currency"),
                    "passengers": raw.get("passengers", []),
                    "slices": raw.get("slices", []),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
