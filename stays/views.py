import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import StaySearchSerializer
from .schema_examples import (
    STAY_SEARCH_EXAMPLE_REQUEST,
    STAY_SEARCH_EXAMPLE_RESPONSE,
    STAY_RATES_EXAMPLE_RESPONSE,
)
from .services.duffel_stays import geocode_location, search_stays, get_stay_rates

logger = logging.getLogger(__name__)


class StaySearchView(APIView):

    @swagger_auto_schema(
        operation_summary="Search hotels by location",
        operation_description=(
            "Search for available hotels/stays using a location name, dates, guest count and rooms.\n\n"
            "The system automatically converts `location_name` to coordinates via OpenStreetMap.\n\n"
            "Use the returned `id` (search result ID) to fetch full room rates via `/stays/rates/`.\n\n"
            "### Example Request\n"
            + STAY_SEARCH_EXAMPLE_REQUEST
            + "\n### Example Response\n"
            + STAY_SEARCH_EXAMPLE_RESPONSE
        ),
        tags=["Stays"],
        request_body=StaySearchSerializer,
        responses={
            200: openapi.Response("List of matched hotel properties with cheapest rate"),
            400: openapi.Response("Validation error or location not found"),
            503: openapi.Response("Duffel API not configured"),
        },
    )
    def post(self, request):
        serializer = StaySearchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        v_data = serializer.validated_data
        location_name = v_data.get("location_name")
        radius = v_data.get("radius", 10)
        check_in = v_data.get("check_in_date").isoformat()
        check_out = v_data.get("check_out_date").isoformat()
        guests = v_data.get("guests")
        rooms = v_data.get("rooms", 1)

        # 1. Geocode
        lat, lng = geocode_location(location_name)
        if lat is None or lng is None:
            return Response(
                {"error": f"Could not find coordinates for location: {location_name}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Search Duffel (returns filtered, shaped data)
        data, error = search_stays(lat, lng, check_in, check_out, guests, rooms, radius)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_200_OK)


class StayRatesView(APIView):

    @swagger_auto_schema(
        operation_summary="Get room rates for a property",
        operation_description=(
            "Fetch all available room types and rates for a specific property.\n\n"
            "Get the `search_result_id` from the `id` field in a `/stays/search/` response.\n\n"
            "Results expire after `expires_at` — re-search if expired.\n\n"
            "### Example Response\n"
            + STAY_RATES_EXAMPLE_RESPONSE
        ),
        tags=["Stays"],
        manual_parameters=[
            openapi.Parameter(
                name="search_result_id",
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                required=True,
                description="The `id` from a stay search result (e.g. srr_0000B5IfJxvta3TIDZa0Ev)",
            )
        ],
        responses={
            200: openapi.Response("Room rates and options for the property"),
            400: openapi.Response("Missing or invalid search_result_id"),
        },
    )
    def post(self, request):
        search_result_id = request.data.get("search_result_id") or request.query_params.get("search_result_id")
        if not search_result_id:
            return Response(
                {"error": "search_result_id is required (pass as query param or JSON body)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        data, error = get_stay_rates(search_result_id)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_200_OK)
