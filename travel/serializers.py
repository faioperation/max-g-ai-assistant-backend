from rest_framework import serializers
import datetime


class FlightSliceSerializer(serializers.Serializer):
    origin = serializers.CharField(
        max_length=3,
        help_text="IATA airport code for origin (e.g. DAC, LHR, JFK)"
    )
    destination = serializers.CharField(
        max_length=3,
        help_text="IATA airport code for destination (e.g. DXB, CDG)"
    )
    departure_date = serializers.DateField(
        help_text="Departure date in YYYY-MM-DD format"
    )


class PassengerSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=["adult", "child", "infant_without_seat"],
        default="adult",
        help_text="Passenger type"
    )


class FlightSearchSerializer(serializers.Serializer):
    slices = FlightSliceSerializer(
        many=True,
        help_text="List of flight legs (one for one-way, two for return)"
    )
    passengers = PassengerSerializer(
        many=True,
        help_text="List of passengers",
        default=[{"type": "adult"}]
    )
    max_results = serializers.IntegerField(
        required=False,
        default=50,
        min_value=1,
        max_value=50,
        help_text="Maximum number of offers to return (default: 50)"
    )


class BookingPassengerSerializer(serializers.Serializer):
    id = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Optional: Passenger ID from the offer. If omitted, backend will auto-map it."
    )
    title = serializers.ChoiceField(
        choices=["mr", "mrs", "ms", "miss", "dr"],
        help_text="Passenger title"
    )
    given_name = serializers.CharField(help_text="First name")
    family_name = serializers.CharField(help_text="Last name / surname")
    born_on = serializers.DateField(
        help_text="Date of birth in YYYY-MM-DD format"
    )
    gender = serializers.ChoiceField(
        choices=["m", "f"],
        help_text="Gender: 'm' or 'f'"
    )
    email = serializers.EmailField(help_text="Passenger email address")
    phone_number = serializers.CharField(
        help_text="Phone number in E.164 format (e.g. +8801641697469)"
    )
    passenger_type = serializers.ChoiceField(
        choices=["adult", "child", "infant_without_seat"],
        default="adult",
        required=False,
        help_text="Passenger type: adult (default), child, or infant_without_seat"
    )
    passport_number = serializers.CharField(
        required=False, 
        allow_blank=True, 
        help_text="Passport number (required for international flights)"
    )
    passport_expiry_date = serializers.DateField(
        required=False, 
        allow_null=True, 
        help_text="Passport expiry date in YYYY-MM-DD format"
    )
    passport_issuing_country = serializers.CharField(
        required=False, 
        allow_blank=True, 
        max_length=2, 
        help_text="2-letter country code (e.g. BD, US)"
    )


class FlightBookSerializer(serializers.Serializer):
    offer_id = serializers.CharField(
        help_text="Duffel offer ID obtained from /flights/search/ (e.g. off_0000Aqn05etwE3zG9RXZwN)"
    )
    passengers = BookingPassengerSerializer(
        many=True,
        help_text="Full passenger details — must match the number of passengers in the offer"
    )
    payment_type = serializers.ChoiceField(
        choices=["balance", "arc_bsp_cash"],
        default="balance",
        required=False,
        help_text="Payment method: 'balance' (Duffel balance) or 'arc_bsp_cash'"
    )


class FlightHoldSerializer(serializers.Serializer):
    offer_id = serializers.CharField(
        help_text="Duffel offer ID obtained from /flights/search/ (e.g. off_0000Aqn05etwE3zG9RXZwN)"
    )
    whatsapp_number = serializers.CharField(
        help_text="User's WhatsApp number for sending payment link and ticket",
        required=True
    )
    passengers = BookingPassengerSerializer(
        many=True,
        help_text="Full passenger details — must match the number of passengers in the offer"
    )
