"""
Duffel API service layer.
Handles all communication with the Duffel air travel API (v2).
"""

import datetime
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DUFFEL_BASE_URL = "https://api.duffel.com"
DUFFEL_AIR_URL = f"{DUFFEL_BASE_URL}/air"
DUFFEL_PAYMENTS_URL = f"{DUFFEL_BASE_URL}/payments"


def get_headers():
    """Build Duffel auth headers. Raises ValueError if token is not set."""
    token = getattr(settings, "DUFFEL_ACCESS_TOKEN", None)
    if not token:
        raise ValueError("Duffel API not configured — set DUFFEL_ACCESS_TOKEN in .env")
    return {
        "Authorization": f"Bearer {token}",
        "Duffel-Version": "v2",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _duffel_error(res):
    """Extract a human-readable error message from a Duffel error response."""
    data = res.json()
    msg = data.get("errors", [{"message": "Duffel error"}])[0].get("message")
    req_id = data.get("meta", {}).get("request_id", "Unknown")
    return msg, req_id


def _format_airport(a):
    return {
        "iata_city_code": a.get("iata_city_code"),
        "city_name": a.get("city_name"),
        "time_zone": a.get("time_zone"),
        "type": a.get("type"),
        "name": a.get("name"),
        "id": a.get("id"),
    }


def _format_offer(raw):
    """Convert a raw Duffel offer object into our clean response schema."""
    formatted_slices = []
    for s in raw.get("slices", []):
        segments = []
        for seg in s.get("segments", []):
            ac = seg.get("aircraft") or {}
            oc = seg.get("operating_carrier") or {}
            segments.append(
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

        formatted_slices.append(
            {
                "fare_brand_name": s.get("fare_brand_name"),
                "segments": segments,
                "origin": _format_airport(s.get("origin") or {}),
                "destination": _format_airport(s.get("destination") or {}),
                "id": s.get("id"),
            }
        )

    own = raw.get("owner") or {}
    return {
        "offer_id": raw.get("id"),
        "total_amount": raw.get("total_amount"),
        "total_currency": raw.get("total_currency"),
        "supported_order_strategies": raw.get("supported_order_strategies", []),
        "expires_at": raw.get("expires_at"),
        "slices": formatted_slices,
        "owner": {
            "iata_code": own.get("iata_code"),
            "name": own.get("name"),
            "id": own.get("id"),
        },
    }


def search_flights(slices_data, passengers_data, max_results=50):
    """
    Search for flights via Duffel.
    Deduplicates results by flight signature (carriers + times).
    """
    headers = get_headers()

    slices_payload = []
    for s in slices_data:
        dep_date = s.get("departure_date")
        if isinstance(dep_date, datetime.date):
            dep_date = dep_date.isoformat()

        slices_payload.append(
            {
                "origin": s.get("origin"),
                "destination": s.get("destination"),
                "departure_date": dep_date,
            }
        )

    # Step 1: Create an offer request
    or_res = requests.post(
        f"{DUFFEL_AIR_URL}/offer_requests",
        headers=headers,
        json={"data": {"slices": slices_payload, "passengers": passengers_data}},
    )
    if or_res.status_code >= 400:
        msg, _ = _duffel_error(or_res)
        return None, msg

    offer_request_id = or_res.json().get("data", {}).get("id")

    # Step 2: Fetch the offers
    offers_res = requests.get(
        f"{DUFFEL_AIR_URL}/offers",
        headers=headers,
        params={"offer_request_id": offer_request_id, "limit": max_results},
    )
    if offers_res.status_code >= 400:
        msg, _ = _duffel_error(offers_res)
        return None, msg

    offers_raw = offers_res.json().get("data", [])
    if offers_raw:
        logger.info("DEBUG: First Raw Duffel Offer: %s", json.dumps(offers_raw[0]))

    # Step 3: Deduplicate by flight signature and format
    seen = set()
    offers = []
    for raw in offers_raw:
        parts = []
        for s in raw.get("slices", []):
            for seg in s.get("segments", []):
                carrier = (seg.get("operating_carrier") or {}).get("iata_code", "")
                parts.append(
                    f"{carrier}-{seg.get('departing_at', '')}-{seg.get('arriving_at', '')}"
                )
        sig = "|".join(parts)
        if sig in seen:
            continue
        seen.add(sig)
        offers.append(_format_offer(raw))

    return [
        {
            "offer_request_id": offer_request_id,
            "offers_count": len(offers),
            "offers": offers,
        }
    ], None


def get_offer(offer_id):
    """Fetch a single Duffel offer."""
    headers = get_headers()
    res = requests.get(f"{DUFFEL_AIR_URL}/offers/{offer_id}", headers=headers)
    if res.status_code >= 400:
        msg, req_id = _duffel_error(res)
        return None, msg
    return res.json()["data"], None


def book_flight(
    offer_id,
    passengers_input,
    payment_type="balance",
    order_type="instant",
    payment_intent_id=None,
):
    """
    Book a flight offer.
    - payment_type="balance"         → charges Duffel account balance (for held orders)
    - payment_type="payment_intent"  → charges card via a Duffel Payment Intent (atomic: charge + ticket in one step)
    - payment_intent_id              → required when payment_type="payment_intent"
    Returns (booking_result_dict, error_dict_or_None).
    """
    headers = get_headers()

    # 1. Fetch offer to get amount and passenger IDs
    offer_res = requests.get(f"{DUFFEL_AIR_URL}/offers/{offer_id}", headers=headers)
    if offer_res.status_code >= 400:
        msg, _ = _duffel_error(offer_res)
        return None, {"error": msg}

    offer_data = offer_res.json().get("data", {})
    total_amount = offer_data.get("total_amount")
    total_currency = offer_data.get("total_currency")
    offer_passengers = offer_data.get("passengers", [])

    # Validate order strategy
    strategies = offer_data.get("supported_order_strategies", ["instant"])
    if order_type not in strategies:
        return (
            None,
            f"Order strategy '{order_type}' is not supported by this carrier. This flight must be booked via: {', '.join(strategies)}",
        )

    # 2. Build clean passenger dicts for Duffel
    duffel_passengers = []
    for idx, p in enumerate(passengers_input):
        offer_pax = offer_passengers[idx] if idx < len(offer_passengers) else {}

        born_on = p.get("born_on")
        if isinstance(born_on, datetime.date):
            born_on = born_on.isoformat()

        import re

        def clean_name(name):
            if not name:
                return ""
            # Keep only letters and spaces
            return re.sub(r"[^a-zA-Z\s]", "", name).strip()

        pax = {
            "id": p.get("id") or offer_pax.get("id"),
            "type": p.get("type") or p.get("passenger_type") or "adult",
            "title": p.get("title", "mr").lower(),
            "given_name": clean_name(p.get("given_name")),
            "family_name": clean_name(p.get("family_name")),
            "born_on": born_on,
            "gender": p.get("gender"),
            "email": p.get("email"),
            "phone_number": p.get("phone_number"),
        }

        passport_num = p.get("passport_number")
        passport_exp = p.get("passport_expiry_date")
        passport_country = p.get("passport_issuing_country")
        if passport_num and passport_exp and passport_country:
            if isinstance(passport_exp, datetime.date):
                passport_exp = passport_exp.isoformat()
            pax["identity_documents"] = [
                {
                    "type": "passport",
                    "unique_identifier": passport_num,
                    "expires_on": passport_exp,
                    "issuing_country_code": passport_country,
                }
            ]

        duffel_passengers.append(pax)

    payload = {
        "data": {
            "type": order_type,
            "selected_offers": [offer_id],
            "passengers": duffel_passengers,
        }
    }

    if order_type == "instant":
        payload["data"]["payments"] = [
            {
                "type": payment_type,
                "currency": total_currency,
                "amount": total_amount,
            }
        ]

    logger.info("Duffel booking payload: %s", json.dumps(payload))

    # 3. Place the order
    res = requests.post(f"{DUFFEL_AIR_URL}/orders", headers=headers, json=payload)
    if res.status_code >= 400:
        msg, req_id = _duffel_error(res)
        return None, {
            "error": msg,
            "duffel_request_id": req_id,
            "hint": "Ensure passenger details are valid (phone in E.164 format, valid passport, etc.).",
        }

    raw = res.json().get("data", {})
    return {
        "order_id": raw.get("id"),
        "booking_reference": raw.get("booking_reference"),
        "status": (
            "awaiting_payment"
            if raw.get("payment_status", {}).get("awaiting_payment")
            else "confirmed"
        ),
        "total_amount": raw.get("total_amount"),
        "total_currency": raw.get("total_currency"),
    }, None


def create_payment_intent(amount, currency):
    """Create a Duffel Payment Intent."""
    headers = get_headers()
    payload = {
        "data": {
            "amount": str(amount),
            "currency": currency,
        }
    }
    res = requests.post(
        f"{DUFFEL_PAYMENTS_URL}/payment_intents", headers=headers, json=payload
    )
    if res.status_code >= 400:
        msg, req_id = _duffel_error(res)
        return None, msg

    data = res.json().get("data", {})
    return {
        "id": data.get("id"),
        "client_token": data.get("client_token"),
    }, None


def get_payment_intent(intent_id):
    """Get a Duffel Payment Intent."""
    headers = get_headers()
    res = requests.get(
        f"{DUFFEL_PAYMENTS_URL}/payment_intents/{intent_id}", headers=headers
    )
    if res.status_code >= 400:
        msg, req_id = _duffel_error(res)
        return None, msg

    data = res.json().get("data", {})
    return data, None


def pay_held_order(order_id, amount, currency, payment_type="balance"):
    """Officially pay for a 'held' order using Duffel balance."""
    headers = get_headers()
    payload = {
        "data": {
            "payment": {
                "type": payment_type,
                "amount": str(amount),
                "currency": currency,
            }
        }
    }
    res = requests.post(
        f"{DUFFEL_AIR_URL}/orders/{order_id}/actions/pay", headers=headers, json=payload
    )
    if res.status_code >= 400:
        msg, req_id = _duffel_error(res)
        return None, msg

    data = res.json().get("data", {})
    return data, None


def get_order_details(order_id):
    """Fetch full details of a Duffel order, including ticket documents."""
    headers = get_headers()
    res = requests.get(f"{DUFFEL_AIR_URL}/orders/{order_id}", headers=headers)
    if res.status_code >= 400:
        msg, req_id = _duffel_error(res)
        return None, msg
    return res.json().get("data", {}), None
