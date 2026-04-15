import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DUFFEL_BASE_URL = "https://api.duffel.com"
DUFFEL_STAYS_URL = f"{DUFFEL_BASE_URL}/stays"


def get_stays_headers():
    """Build Duffel Stays auth headers (v2)."""
    token = getattr(settings, "DUFFEL_ACCESS_TOKEN", None)
    if not token:
        raise ValueError("Duffel API not configured — set DUFFEL_ACCESS_TOKEN in .env")
    return {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": "v2",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def geocode_location(location_name):
    """
    Convert a location name (e.g. 'Dhaka') to lat/lng using Nominatim (OpenStreetMap).
    Returns (lat, lng) or (None, None).
    """
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": location_name, "format": "json", "limit": 1}
        headers = {"User-Agent": "Max_G_Travel_Assistant/1.0"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        logger.error(f"Geocoding error for {location_name}: {str(e)}")
    return None, None


def format_stay_result(result: dict) -> dict:
    """
    Filter and reshape a single stay search result to only the fields we need.
    """
    accommodation = result.get("accommodation") or {}
    location = accommodation.get("location") or {}
    address = location.get("address") or {}
    brand = accommodation.get("brand") or {}
    chain = accommodation.get("chain") or {}
    check_in_info = accommodation.get("check_in_information") or {}

    return {
        "id": result.get("id"),
        "check_in_date": result.get("check_in_date"),
        "check_out_date": result.get("check_out_date"),
        "expires_at": result.get("expires_at"),
        "rooms": result.get("rooms"),
        # Pricing
        "cheapest_rate_total_amount": result.get("cheapest_rate_total_amount"),
        "cheapest_rate_currency": result.get("cheapest_rate_currency"),
        # Accommodation
        "accommodation": {
            "id": accommodation.get("id"),
            "name": accommodation.get("name"),
            "phone_number": accommodation.get("phone_number"),
            "email": accommodation.get("email"),
            "supported_loyalty_programme": accommodation.get(
                "supported_loyalty_programme"
            ),
            "payment_instruction_supported": accommodation.get(
                "payment_instruction_supported"
            ),
            # Brand & Chain
            "brand": (
                {
                    "id": brand.get("id"),
                    "name": brand.get("name"),
                }
                if brand
                else None
            ),
            "chain": (
                {
                    "name": chain.get("name"),
                }
                if chain
                else None
            ),
            # Location
            "location": {
                "address": {
                    "line_one": address.get("line_one"),
                    "city_name": address.get("city_name"),
                    "postal_code": address.get("postal_code"),
                    "region": address.get("region"),
                    "country_code": address.get("country_code"),
                }
            },
            # Check-in info
            "check_in_information": {
                "check_in_after_time": check_in_info.get("check_in_after_time"),
                "check_in_before_time": check_in_info.get("check_in_before_time"),
                "check_out_before_time": check_in_info.get("check_out_before_time"),
            },
            # All amenities as a compact comma-separated string
            "amenities": ", ".join(
                amenity.get("description", "")
                for amenity in accommodation.get("amenities", [])
                if amenity.get("description")
            ),
        },
    }


def search_stays(lat, lng, check_in, check_out, guests, rooms=1, radius=10):
    """
    Search for accommodations via Duffel Stays.
    Returns filtered and shaped data.
    """
    headers = get_stays_headers()
    payload = {
        "data": {
            "rooms": rooms,
            "location": {
                "radius": radius,
                "geographic_coordinates": {"latitude": lat, "longitude": lng},
            },
            "guests": guests,
            "check_out_date": check_out,
            "check_in_date": check_in,
        }
    }

    response = requests.post(
        f"{DUFFEL_STAYS_URL}/search", headers=headers, json=payload
    )
    if response.status_code >= 400:
        logger.error(f"Duffel Stays Search Error: {response.text}")
        try:
            return None, response.json().get("errors", [{"message": "Unknown error"}])[
                0
            ].get("message")
        except Exception:
            return None, response.text or "Unknown error from Duffel"

    raw = response.json().get("data", {})
    results = raw.get("results", []) if isinstance(raw, dict) else []

    shaped = {
        "created_at": raw.get("created_at") if isinstance(raw, dict) else None,
        "results": [format_stay_result(r) for r in results],
    }
    return shaped, None


def format_stay_rates(data: dict) -> dict:
    """
    Filter and reshape the rates API response to only the fields we need.
    """
    accommodation = data.get("accommodation") or {}
    location = accommodation.get("location") or {}
    address = location.get("address") or {}
    chain = accommodation.get("chain") or {}
    check_in_info = accommodation.get("check_in_information") or {}

    # Format each room with only needed fields
    formatted_rooms = []
    for room in accommodation.get("rooms", []):
        formatted_rates = []
        for rate in room.get("rates", []):
            formatted_rates.append({
                "id": rate.get("id"),
                "quantity_available": rate.get("quantity_available"),
                "board_type": rate.get("board_type"),
                "payment_type": rate.get("payment_type"),
                "total_amount": rate.get("total_amount"),
                "total_currency": rate.get("total_currency"),
                "available_payment_methods": ", ".join(
                    rate.get("available_payment_methods", [])
                ),
                "expires_at": rate.get("expires_at"),
                # conditions as comma-separated titles
                "conditions": ", ".join(
                    c.get("title", "")
                    for c in rate.get("conditions", [])
                    if c.get("title")
                ),
            })

        formatted_rooms.append({
            "name": room.get("name"),
            "beds": [
                {"type": b.get("type"), "count": b.get("count")}
                for b in room.get("beds", [])
            ],
            "rates": formatted_rates,
        })

    return {
        "id": data.get("id"),
        "check_in_date": data.get("check_in_date"),
        "check_out_date": data.get("check_out_date"),
        "expires_at": data.get("expires_at"),
        "rooms": data.get("rooms"),
        "accommodation": {
            "id": accommodation.get("id"),
            "name": accommodation.get("name"),
            "phone_number": accommodation.get("phone_number"),
            "email": accommodation.get("email"),
            "supported_loyalty_programme": accommodation.get("supported_loyalty_programme"),
            "review_score": accommodation.get("review_score"),
            "review_count": accommodation.get("review_count"),
            "chain": {"name": chain.get("name")} if chain else None,
            "location": {
                "address": {
                    "line_one": address.get("line_one"),
                    "city_name": address.get("city_name"),
                    "region": address.get("region"),
                }
            },
            "check_in_information": {
                "check_in_after_time": check_in_info.get("check_in_after_time"),
                "check_in_before_time": check_in_info.get("check_in_before_time"),
                "check_out_before_time": check_in_info.get("check_out_before_time"),
            },
            # Amenities as compact comma-separated string
            "amenities": ", ".join(
                a.get("description", "")
                for a in accommodation.get("amenities", [])
                if a.get("description")
            ),
            "rooms": formatted_rooms,
        },
    }


def get_stay_rates(search_result_id):
    """
    Fetch available rates for a specific stay search result.
    Duffel Stays API: POST /stays/search_results/{id}/actions/fetch_all_rates
    """
    headers = get_stays_headers()
    url = f"{DUFFEL_STAYS_URL}/search_results/{search_result_id}/actions/fetch_all_rates"

    # Duffel Stays rates endpoint requires POST (not GET)
    response = requests.post(url, headers=headers, json={})
    if response.status_code >= 400:
        logger.error(f"Duffel Stays Rates Error: {response.text}")
        try:
            return None, response.json().get("errors", [{"message": "Unknown error"}])[
                0
            ].get("message")
        except Exception:
            return None, response.text or "Unknown error from Duffel"

    raw = response.json().get("data")
    if not raw:
        return None, "No data returned from Duffel"

    return format_stay_rates(raw), None
