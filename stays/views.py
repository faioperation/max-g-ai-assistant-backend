import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema

from .serializers import StaySearchSerializer
from .services.duffel_stays import geocode_location, search_stays, get_stay_rates

logger = logging.getLogger(__name__)

class StaySearchView(APIView):
    """
    Search for properties based on location name.
    1. Geocode location name to lat/lng.
    2. Call Duffel Stays Search API.
    """
    @swagger_auto_schema(
        request_body=StaySearchSerializer,
        responses={200: "Properties Result", 400: "Bad Request", 500: "Server Error"}
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

        # 2. Search Duffel
        data, error = search_stays(
            lat, lng, check_in, check_out, guests, rooms, radius
        )
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_200_OK)

class StayRatesView(APIView):
    """
    Get all rates and details for a specific property (search result).
    """
    def get(self, request):
        search_result_id = request.query_params.get("search_result_id")
        if not search_result_id:
            return Response(
                {"error": "search_result_id query param is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        data, error = get_stay_rates(search_result_id)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_200_OK)
