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
```
"""
