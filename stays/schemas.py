STAY_SEARCH_EXAMPLE_REQUEST = """
```json
{
  "location_name": "Dhaka",
  "check_in_date": "2026-10-25",
  "check_out_date": "2026-10-30",
  "guests": [
    { "type": "adult" }
  ],
  "rooms": 1
}
```

**Notes:**
- `location_name` — city or area name, e.g. `"Dhaka"`, `"Dubai"`, `"London"`
- `guests` — one object per guest. Supported types: `adult`, `child`
- `radius` — search radius in **kilometers** from the city center (default: `10`)
- `rooms` — number of rooms required (default: `1`)
"""

STAY_SEARCH_EXAMPLE_RESPONSE = """
```json
{
  "created_at": "2026-04-15T00:02:19.700415Z",
  "results": [
    {
      "id": "srr_0000B5IfJxvta3TIDZa0Ev",
      "check_in_date": "2026-10-25",
      "check_out_date": "2026-10-30",
      "expires_at": "2026-04-15T00:41:22.539878Z",
      "rooms": 1,
      "cheapest_rate_total_amount": "434.79",
      "cheapest_rate_currency": "GBP",
      "cheapest_rate_public_amount": "434.79",
      "cheapest_rate_public_currency": "GBP",
      "cheapest_rate_base_amount": "322.83",
      "cheapest_rate_base_currency": "GBP",
      "cheapest_rate_due_at_accommodation_amount": "0.00",
      "cheapest_rate_due_at_accommodation_currency": "USD",
      "accommodation": {
        "id": "acc_0000AWPt1KoOUyQ7QZFdQ4",
        "name": "Holiday Inn Dhaka City Centre by IHG",
        "phone_number": "880-9638-555666",
        "email": null,
        "supported_loyalty_programme": "ihg_one_rewards",
        "payment_instruction_supported": false,
        "brand": { "id": "bra_Vz5sccWuhDPm8qiuVJGKid", "name": "Holiday Inn" },
        "chain": { "name": "InterContinental Hotels Group" },
        "location": {
          "address": {
            "line_one": "23 Shahid Tajuddin Ahmed Sharani, Tejgaon",
            "city_name": "Dhaka",
            "postal_code": "1208",
            "region": "Dhaka Division",
            "country_code": "BD"
          }
        },
        "check_in_information": {
          "check_in_after_time": "14:00",
          "check_in_before_time": null,
          "check_out_before_time": "12:00"
        },
        "amenities": "Laundry Service, Wi-Fi, Parking, Gym, Spa, Swimming Pool, Restaurant, Room Service, Concierge, 24-Hour Front Desk"
      }
    }
  ]
}
```
"""

STAY_HOLD_EXAMPLE_REQUEST = """
```json
{
  "rate_id": "rat_0000AJyeTUCEoY5PhVPN8k_0",
  "guests": [
    {
      "given_name": "Ariful",
      "family_name": "Islam",
      "email": "arif.fireai@gmail.com"
    }
  ],
  "phone_number": "+8801912345678",
  "email": "arif.fireai@gmail.com",
  "whatsapp_number": "+8801912345678"
}
```
"""

STAY_HOLD_EXAMPLE_RESPONSE = """
```json
{
  "checkout_url": "https://max-g.example.com/api/v1/stays/checkout/pi_123abc/",
  "quote_id": "quo_0000AabcXYZ123",
  "amount": "150.00",
  "currency": "USD"
}
```
"""
STAY_RATES_EXAMPLE_RESPONSE = """
```json
{
  "id": "srr_0000B5IfJxvta3TIDZa0Ev",
  "rates": [
    {
      "id": "rat_0000xxx",
      "room_type": "Deluxe King Room",
      "board_type": "room_only",
      "total_amount": "434.79",
      "currency": "GBP",
      "cancellation_policy": "non_refundable"
    },
    {
      "id": "rat_0000yyy",
      "room_type": "Standard Double Room",
      "board_type": "breakfast_included",
      "total_amount": "388.00",
      "currency": "GBP",
      "cancellation_policy": "free_cancellation"
    }
  ]
}
}
```
"""

from drf_yasg import openapi
from stays.serializers import StaySearchSerializer, StayHoldSerializer

STAY_SEARCH_SCHEMA = {
    "operation_summary": "Search hotels by location",
    "operation_description": (
        "Search for available hotels/stays using a location name, dates, guest count and rooms.\n\n"
        "The system automatically converts `location_name` to coordinates via OpenStreetMap.\n\n"
        "Use the returned `id` (search result ID) to fetch full room rates via `/stays/rates/`.\n\n"
        "### Example Request\n"
        + STAY_SEARCH_EXAMPLE_REQUEST
        + "\n### Example Response\n"
        + STAY_SEARCH_EXAMPLE_RESPONSE
    ),
    "tags": ["Stays"],
    "request_body": StaySearchSerializer,
    "responses": {
        200: openapi.Response("List of matched hotel properties with cheapest rate"),
        400: openapi.Response("Validation error or location not found"),
        503: openapi.Response("Duffel API not configured"),
    },
}

STAY_RATES_SCHEMA = {
    "operation_summary": "Get room rates for a property",
    "operation_description": (
        "Fetch all available room types and rates for a specific property.\n\n"
        "Get the `search_result_id` from the `id` field in a `/stays/search/` response.\n\n"
        "Results expire after `expires_at` — re-search if expired.\n\n"
        "### Example Response\n" + STAY_RATES_EXAMPLE_RESPONSE
    ),
    "tags": ["Stays"],
    "manual_parameters": [
        openapi.Parameter(
            name="search_result_id",
            in_=openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            required=True,
            description="The `id` from a stay search result (e.g. srr_0000B5IfJxvta3TIDZa0Ev)",
        )
    ],
    "responses": {
        200: openapi.Response("Room rates and options for the property"),
        400: openapi.Response("Missing or invalid search_result_id"),
    },
}

STAY_HOLD_SCHEMA = {
    "operation_summary": "Hold a stay and create payment intent",
    "operation_description": (
        "Reserve a hotel room using a Duffel `rate_id` and generate a Payment Intent for checkout.\n\n"
        "Returns a `checkout_url` which should be sent to the user on WhatsApp.\n\n"
        "### Example Request\n"
        + STAY_HOLD_EXAMPLE_REQUEST
        + "\n### Example Response\n"
        + STAY_HOLD_EXAMPLE_RESPONSE
    ),
    "tags": ["Stays"],
    "request_body": openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "rate_id": openapi.Schema(type=openapi.TYPE_STRING, description="Rate ID"),
            "guests": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "given_name": openapi.Schema(type=openapi.TYPE_STRING),
                        "family_name": openapi.Schema(type=openapi.TYPE_STRING),
                        "email": openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            ),
            "phone_number": openapi.Schema(type=openapi.TYPE_STRING),
            "email": openapi.Schema(type=openapi.TYPE_STRING),
            "whatsapp_number": openapi.Schema(type=openapi.TYPE_STRING),
        },
    ),
    "responses": {
        200: openapi.Response("Payment checkout link generated"),
        400: openapi.Response("Validation or Duffel API error"),
    },
}

STAY_PAYMENT_CHECKOUT_SCHEMA = {
    "operation_summary": "Render secure checkout page",
    "operation_description": "Serves the HTML checkout page for Duffel Payments.",
    "tags": ["Stays Payments"],
    "responses": {200: "HTML page"},
}

STAY_PAYMENT_SUCCESS_SCHEMA = {
    "operation_summary": "Handle successful Duffel payment",
    "operation_description": "Called by the frontend when Duffel payment succeeds. Confirms the stay booking.",
    "tags": ["Stays Payments"],
    "request_body": openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "intent_id": openapi.Schema(
                type=openapi.TYPE_STRING, description="Payment Intent ID"
            )
        },
    ),
    "responses": {200: "Booking ID and success"},
}
