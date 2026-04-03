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

HOLD_EXAMPLE_REQUEST = """
```json
{
  "offer_id": "off_0000B4lQ03f7GsWITc3MlW",
  "whatsapp_number": "+8801641697469",
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
"""

HOLD_EXAMPLE_RESPONSE = """
```json
{
  "checkout_url": "http://your-domain.com/api/v1/travel/checkout/pi_123456/",
  "order_id": "ord_0000B4mX98d...",
  "amount": "798.10",
  "currency": "USD"
}
```
"""
