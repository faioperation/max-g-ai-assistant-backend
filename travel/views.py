import datetime
import json
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from travel.serializers import FlightSearchSerializer, FlightBookSerializer


DUFFEL_API_URL = "https://api.duffel.com/air"


def _duffel_headers():
    token = getattr(settings, "DUFFEL_ACCESS_TOKEN", None)
    if not token:
        raise ValueError("Duffel API not configured — set DUFFEL_ACCESS_TOKEN in .env")
    return {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": "v2",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


class FlightSearchView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Search for available flights",
        operation_description=(
            "Search for available flight offers using the Duffel API.\n\n"
            "Use the returned `offer_id` from each offer to call `/flights/book/`.\n\n"
            "### Example Request Payload\n"
            "```json\n"
            "{\n"
            '  "slices": [\n'
            "    {\n"
            '      "origin": "DAC",\n'
            '      "destination": "DXB",\n'
            '      "departure_date": "2026-05-01"\n'
            "    }\n"
            "  ],\n"
            '  "passengers": [\n'
            '    { "type": "adult" }\n'
            "  ],\n"
            '  "max_results": 10\n'
            "}\n"
            "```\n\n"
            "### Example Response Payload\n"
            "```json\n"
            "[\n"
            "  {\n"
            '    "offer_request_id": "orq_0000B4...",\n'
            '    "offers_count": 10,\n'
            '    "offers": [\n'
            "      {\n"
            '        "offer_id": "off_00...",\n'
            '        "total_amount": "798.10",\n'
            '        "total_currency": "USD",\n'
            '        "expires_at": "2026-03-29T23:44:13Z",\n'
            '        "slices": [\n'
            "          {\n"
            '            "fare_brand_name": "Economy Flex",\n'
            '            "segments": [\n'
            "              {\n"
            '                "aircraft": { "iata_code": "32N", "name": "Airbus", "id": "arc_000" },\n'
            '                "departing_at": "2026-05-01T11:45:00",\n'
            '                "arriving_at": "2026-05-01T14:35:00",\n'
            '                "operating_carrier": { "iata_code": "AI", "name": "Air India", "id": "arl_000" }\n'
            "              }\n"
            "            ],\n"
            '            "destination": { "iata_city_code": "LON", "city_name": "London", "time_zone": "Europe/London", "type": "airport", "name": "Heathrow Airport", "id": "arp_lhr" },\n'
            '            "origin": { "iata_city_code": "DAC", "city_name": "Dhaka", "time_zone": "Asia/Dhaka", "type": "airport", "name": "Dhaka Shahjalal", "id": "arp_dac" },\n'
            '            "id": "sli_00..."\n'
            "          }\n"
            "        ],\n"
            '        "owner": { "iata_code": "AI", "name": "Air India", "id": "arl_00..." }\n'
            "      }\n"
            "    ]\n"
            "  }\n"
            "]\n"
            "```"
        ),
        tags=["Travel — Flights"],
        request_body=FlightSearchSerializer,
        responses={
            200: openapi.Response("List of available offers"),
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
            return Response(
                {"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        try:
            slices_data = serializer.validated_data["slices"]
            passengers_data = serializer.validated_data["passengers"]
            max_results = serializer.validated_data.get("max_results", 15)

            slices_payload = [
                {
                    "origin": s["origin"],
                    "destination": s["destination"],
                    "departure_date": (
                        s["departure_date"].isoformat()
                        if isinstance(s["departure_date"], datetime.date)
                        else s["departure_date"]
                    ),
                }
                for s in slices_data
            ]

            payload = {
                "data": {"slices": slices_payload, "passengers": passengers_data}
            }

            # 1. Create Offer Request
            or_res = requests.post(
                f"{DUFFEL_API_URL}/offer_requests", headers=headers, json=payload
            )
            if or_res.status_code >= 400:
                err_data = or_res.json()
                msg = err_data.get("errors", [{"message": "Duffel error"}])[0].get(
                    "message"
                )
                return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

            offer_request_id = or_res.json()["data"]["id"]

            # 2. List Offers
            offers_res = requests.get(
                f"{DUFFEL_API_URL}/offers",
                headers=headers,
                params={"offer_request_id": offer_request_id, "limit": max_results},
            )

            if offers_res.status_code >= 400:
                err_data = offers_res.json()
                msg = err_data.get("errors", [{"message": "Duffel error"}])[0].get(
                    "message"
                )
                return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

            offers_raw = offers_res.json().get("data", [])

            offers = []
            seen_flight_signatures = set()

            for raw in offers_raw:
                # 1. Create a unique signature to prevent duplicate flights (same plane, different fare)
                signature_parts = []
                for s in raw.get("slices", []):
                    for seg in s.get("segments", []):
                        carrier = seg.get("operating_carrier", {}).get("iata_code", "")
                        dep = seg.get("departing_at", "")
                        arr = seg.get("arriving_at", "")
                        signature_parts.append(f"{carrier}-{dep}-{arr}")

                signature = "|".join(signature_parts)
                if signature in seen_flight_signatures:
                    continue  # We already have this exact flight (likely a cheaper fare class)
                seen_flight_signatures.add(signature)

                # 2. Extract exactly the formatted data requested
                formatted_slices = []
                for s in raw.get("slices", []):
                    formatted_segments = []
                    for seg in s.get("segments", []):
                        ac = seg.get("aircraft", {}) or {}
                        oc = seg.get("operating_carrier", {}) or {}

                        formatted_segments.append(
                            {
                                "aircraft": {
                                    "iata_code": ac.get("iata_code"),
                                    "name": ac.get("name"),
                                    "id": ac.get("id"),
                                },
                                "departing_at": seg.get("departing_at"),
                                "arriving_at": seg.get("arriving_at"),
                                "operating_carrier": {
                                    "iata_code": oc.get("iata_code"),
                                    "name": oc.get("name"),
                                    "id": oc.get("id"),
                                },
                            }
                        )

                    o = s.get("origin", {}) or {}
                    d = s.get("destination", {}) or {}

                    formatted_slices.append(
                        {
                            "fare_brand_name": s.get("fare_brand_name"),
                            "segments": formatted_segments,
                            "destination": {
                                "iata_city_code": d.get("iata_city_code"),
                                "city_name": d.get("city_name"),
                                "time_zone": d.get("time_zone"),
                                "type": d.get("type"),
                                "name": d.get("name"),
                                "id": d.get("id"),
                            },
                            "origin": {
                                "iata_city_code": o.get("iata_city_code"),
                                "city_name": o.get("city_name"),
                                "time_zone": o.get("time_zone"),
                                "type": o.get("type"),
                                "name": o.get("name"),
                                "id": o.get("id"),
                            },
                            "id": s.get("id"),
                        }
                    )

                own = raw.get("owner", {}) or {}
                offers.append(
                    {
                        "offer_id": raw.get("id"),
                        "total_amount": raw.get("total_amount"),
                        "total_currency": raw.get("total_currency"),
                        "expires_at": raw.get("expires_at"),
                        "slices": formatted_slices,
                        "owner": {
                            "iata_code": own.get("iata_code"),
                            "name": own.get("name"),
                            "id": own.get("id"),
                        },
                    }
                )

            return Response(
                [
                    {
                        "offer_request_id": offer_request_id,
                        "offers_count": len(offers),
                        "offers": offers,
                    }
                ],
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
            "**Note on Passenger IDs:** You DO NOT need to figure out passenger IDs or the exact total amount. Just provide the user details, and the backend handles the IDs and payment mapping automatically.\n\n"
            "### Example Request Payload\n"
            "```json\n"
            "{\n"
            '  "offer_id": "off_0000B4lQ03f7GsWITc3MlW",\n'
            '  "passengers": [\n'
            "    {\n"
            '      "title": "mr",\n'
            '      "given_name": "Arif",\n'
            '      "family_name": "Rahman",\n'
            '      "born_on": "1990-01-15",\n'
            '      "gender": "m",\n'
            '      "email": "arif@example.com",\n'
            '      "phone_number": "+8801641669746",\n'
            '      "passport_number": "A1234567",\n'
            '      "passport_expiry_date": "2030-10-15",\n'
            '      "passport_issuing_country": "BD"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "```\n\n"
            "### Example Response Payload\n"
            "```json\n"
            "{\n"
            '  "order_id": "ord_0000B4mX98d...",\n'
            '  "booking_reference": "XYZ123",\n'
            '  "status": "confirmed",\n'
            '  "total_amount": "798.10",\n'
            '  "total_currency": "USD"\n'
            "}\n"
            "```"
        ),
        tags=["Travel — Flights"],
        request_body=FlightBookSerializer,
        responses={
            200: openapi.Response("Booking confirmed"),
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
            return Response(
                {"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        try:
            offer_id = serializer.validated_data["offer_id"]
            passengers_input = serializer.validated_data["passengers"]
            payment_type = serializer.validated_data.get("payment_type", "balance")

            # 1. Fetch the actual offer to get EXACT total_amount and passenger IDs
            offer_res = requests.get(
                f"{DUFFEL_API_URL}/offers/{offer_id}", headers=headers
            )
            if offer_res.status_code >= 400:
                err_data = offer_res.json()
                msg = err_data.get(
                    "errors", [{"message": "Invalid or expired offer_id"}]
                )[0].get("message")
                return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

            offer_data = offer_res.json().get("data", {})
            total_amount = offer_data.get("total_amount")
            total_currency = offer_data.get("total_currency")
            offer_passengers = offer_data.get("passengers", [])

            # 2. Map passenger IDs to the user's passenger input
            for idx, p in enumerate(passengers_input):
                if not p.get("id") and idx < len(offer_passengers):
                    p["id"] = offer_passengers[idx].get("id")

                if isinstance(p.get("born_on"), datetime.date):
                    p["born_on"] = p["born_on"].isoformat()

                # 2.1 Handle optional identity documents (Passports)
                passport_num = p.pop("passport_number", None)
                passport_exp = p.pop("passport_expiry_date", None)
                passport_country = p.pop("passport_issuing_country", None)

                if passport_num and passport_exp and passport_country:
                    if isinstance(passport_exp, datetime.date):
                        passport_exp = passport_exp.isoformat()
                    p["identity_documents"] = [
                        {
                            "document_type": "passport",
                            "unique_identifier": passport_num,
                            "expires_on": passport_exp,
                            "issuing_country_code": passport_country,
                        }
                    ]

            payload = {
                "data": {
                    "type": "instant",
                    "selected_offers": [offer_id],
                    "passengers": passengers_input,
                    "payments": [
                        {
                            "type": payment_type,
                            "currency": total_currency,
                            "amount": total_amount,
                        }
                    ],
                }
            }

            # 3. Execute the order
            res = requests.post(
                f"{DUFFEL_API_URL}/orders", headers=headers, json=payload
            )

            if res.status_code >= 400:
                err_data = res.json()
                msg = err_data.get("errors", [{"message": "Duffel booking error"}])[
                    0
                ].get("message")
                req_id = err_data.get("meta", {}).get("request_id", "Unknown")
                return Response(
                    {
                        "error": msg,
                        "duffel_request_id": req_id,
                        "hint": "If this is a Duffel 500 error, ensure the passenger details (like phone format E.164) are perfectly valid.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            raw = res.json().get("data", {})

            # 4. Clean formatted response for the user
            return Response(
                {
                    "order_id": raw.get("id"),
                    "booking_reference": raw.get("booking_reference"),
                    "status": (
                        "awaiting_payment"
                        if raw.get("payment_status", {}).get("awaiting_payment")
                        else "confirmed"
                    ),
                    "total_amount": raw.get("total_amount"),
                    "total_currency": raw.get("total_currency"),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
