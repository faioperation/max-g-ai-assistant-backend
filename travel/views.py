import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from travel.serializers import FlightBookSerializer, FlightSearchSerializer
from travel.services.duffel import book_flight, get_headers, search_flights

logger = logging.getLogger(__name__)

SEARCH_EXAMPLE_REQUEST = """
```json
{
  "slices": [
    { "origin": "DAC", "destination": "DXB", "departure_date": "2026-05-01" }
  ],
  "passengers": [
    { "type": "adult" }
  ]
}
```
"""

SEARCH_EXAMPLE_RESPONSE = """
```json
[
  {
    "offer_request_id": "orq_0000B4...",
    "offers_count": 10,
    "offers": [
      {
        "offer_id": "off_00...",
        "total_amount": "798.10",
        "total_currency": "USD",
        "expires_at": "2026-03-29T23:44:13Z",
        "slices": [
          {
            "fare_brand_name": "Economy Flex",
            "segments": [
              {
                "aircraft": { "iata_code": "32N", "name": "Airbus A320neo", "id": "arc_000" },
                "departing_at": "2026-05-01T11:45:00",
                "arriving_at": "2026-05-01T14:35:00",
                "operating_carrier": { "iata_code": "AI", "name": "Air India", "id": "arl_000" }
              }
            ],
            "origin": { "iata_city_code": "DAC", "city_name": "Dhaka", "name": "Shahjalal Intl", "id": "arp_dac" },
            "destination": { "iata_city_code": "DXB", "city_name": "Dubai", "name": "Dubai Intl", "id": "arp_dxb" },
            "id": "sli_00..."
          }
        ],
        "owner": { "iata_code": "AI", "name": "Air India", "id": "arl_00..." }
      }
    ]
  }
]
```
"""

BOOK_EXAMPLE_REQUEST = """
```json
{
  "offer_id": "off_0000B4lQ03f7GsWITc3MlW",
  "passengers": [
    {
      "type": "adult",
      "title": "mr",
      "given_name": "Arif",
      "family_name": "Rahman",
      "born_on": "1990-01-15",
      "gender": "m",
      "email": "arif@example.com",
      "phone_number": "+8801641697469",
      "passport_number": "A1234567",
      "passport_expiry_date": "2030-10-15",
      "passport_issuing_country": "BD"
    }
  ]
}
```

**Notes:**
- `type` — passenger type: `adult` (default), `child`, or `infant_without_seat`
- `passport_*` fields are **optional** (required for international flights in production)
- You do NOT need to pass passenger IDs or payment amount — the backend resolves them automatically
"""

BOOK_EXAMPLE_RESPONSE = """
```json
{
  "order_id": "ord_0000B4mX98d...",
  "booking_reference": "XYZ123",
  "status": "confirmed",
  "total_amount": "798.10",
  "total_currency": "USD"
}
```
"""


class FlightSearchView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Search for available flights",
        operation_description=(
            "Search for available flight offers via Duffel API. "
            "Returns a deduplicated list of offers formatted for display.\n\n"
            "Use the returned `offer_id` to call `/flights/book/`.\n\n"
            "### Example Request\n" + SEARCH_EXAMPLE_REQUEST +
            "\n### Example Response\n" + SEARCH_EXAMPLE_RESPONSE
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
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

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
        operation_summary="Book a flight offer",
        operation_description=(
            "Confirm and book a flight using a Duffel `offer_id` from `/flights/search/`.\n\n"
            "### Example Request\n" + BOOK_EXAMPLE_REQUEST +
            "\n### Example Response\n" + BOOK_EXAMPLE_RESPONSE
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
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

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
