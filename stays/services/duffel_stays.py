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
        params = {
            "q": location_name,
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": "Max_G_Travel_Assistant/1.0"
        }
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        logger.error(f"Geocoding error for {location_name}: {str(e)}")
    return None, None

def search_stays(lat, lng, check_in, check_out, guests, rooms=1, radius=10):
    """
    Search for accommodations via Duffel Stays.
    """
    headers = get_stays_headers()
    payload = {
        "data": {
            "rooms": rooms,
            "location": {
                "radius": radius,
                "geographic_coordinates": {
                    "latitude": lat,
                    "longitude": lng
                }
            },
            "guests": guests,
            "check_out_date": check_out,
            "check_in_date": check_in
        }
    }
    
    response = requests.post(f"{DUFFEL_STAYS_URL}/search", headers=headers, json=payload)
    if response.status_code >= 400:
        logger.error(f"Duffel Stays Search Error: {response.text}")
        try:
            return None, response.json().get("errors", [{"message": "Unknown error"}])[0].get("message")
        except Exception:
            return None, response.text or "Unknown error from Duffel"
    
    return response.json().get("data"), None

def get_stay_rates(search_result_id):
    """
    Fetch rates for a specific stay search result.
    """
    headers = get_stays_headers()
    url = f"{DUFFEL_STAYS_URL}/search_results/{search_result_id}/rates"
    
    response = requests.get(url, headers=headers)
    if response.status_code >= 400:
        logger.error(f"Duffel Stays Rates Error: {response.text}")
        try:
            return None, response.json().get("errors", [{"message": "Unknown error"}])[0].get("message")
        except Exception:
            return None, response.text or "Unknown error from Duffel"
    
    return response.json().get("data"), None
