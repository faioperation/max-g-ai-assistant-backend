from rest_framework import serializers


# ─────────────────────────────────────────
#  REQUEST SERIALIZERS
# ─────────────────────────────────────────

class StayGuestSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=["adult", "child"],
        default="adult",
        help_text="Guest type: 'adult' or 'child'"
    )


class StaySearchSerializer(serializers.Serializer):
    location_name = serializers.CharField(
        help_text="Name of the city or area to search in (e.g. 'Dhaka', 'New York')"
    )
    check_in_date = serializers.DateField(
        help_text="Check-in date in YYYY-MM-DD format"
    )
    check_out_date = serializers.DateField(
        help_text="Check-out date in YYYY-MM-DD format"
    )
    guests = StayGuestSerializer(
        many=True,
        default=[{"type": "adult"}],
        help_text="List of guests. Add one object per guest with their type."
    )
    rooms = serializers.IntegerField(
        default=1,
        min_value=1,
        help_text="Number of rooms required"
    )
    radius = serializers.IntegerField(
        default=10,
        min_value=1,
        help_text="Search radius in kilometers from the location center"
    )


# ─────────────────────────────────────────
#  RESPONSE SERIALIZERS (Swagger docs only)
# ─────────────────────────────────────────

class AmenitySerializer(serializers.Serializer):
    type = serializers.CharField(help_text="Amenity type key (e.g. 'wifi', 'gym', 'pool')")
    description = serializers.CharField(help_text="Human-readable amenity label")


class AddressSerializer(serializers.Serializer):
    line_one = serializers.CharField(help_text="Street address")
    city_name = serializers.CharField(help_text="City name")
    postal_code = serializers.CharField(help_text="Postal / ZIP code")
    region = serializers.CharField(help_text="State or division")
    country_code = serializers.CharField(help_text="ISO 3166-1 alpha-2 country code (e.g. 'BD')")


class LocationSerializer(serializers.Serializer):
    address = AddressSerializer()


class CheckInInformationSerializer(serializers.Serializer):
    check_in_after_time = serializers.CharField(
        help_text="Earliest check-in time (e.g. '14:00')", allow_null=True
    )
    check_in_before_time = serializers.CharField(
        help_text="Latest check-in time, if any", allow_null=True
    )
    check_out_before_time = serializers.CharField(
        help_text="Checkout deadline (e.g. '12:00')", allow_null=True
    )


class BrandSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="Brand ID")
    name = serializers.CharField(help_text="Brand name (e.g. 'Holiday Inn')")


class ChainSerializer(serializers.Serializer):
    name = serializers.CharField(help_text="Hotel chain name (e.g. 'InterContinental Hotels Group')")


class AccommodationSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="Accommodation ID")
    name = serializers.CharField(help_text="Full property name")
    phone_number = serializers.CharField(allow_null=True, help_text="Hotel contact number")
    email = serializers.CharField(allow_null=True, help_text="Hotel email address")
    supported_loyalty_programme = serializers.CharField(
        allow_null=True, help_text="Supported loyalty programme (e.g. 'ihg_one_rewards')"
    )
    payment_instruction_supported = serializers.BooleanField(
        help_text="Whether the property supports payment instructions"
    )
    brand = BrandSerializer(allow_null=True)
    chain = ChainSerializer(allow_null=True)
    location = LocationSerializer()
    check_in_information = CheckInInformationSerializer()
    amenities = AmenitySerializer(
        many=True,
        help_text="All available amenities for this property"
    )


class StayResultSerializer(serializers.Serializer):
    id = serializers.CharField(help_text="Search result ID (use this to fetch rates)")
    check_in_date = serializers.DateField(help_text="Check-in date")
    check_out_date = serializers.DateField(help_text="Check-out date")
    expires_at = serializers.DateTimeField(help_text="Expiry time of this search result")
    rooms = serializers.IntegerField(help_text="Number of rooms")

    # Pricing
    cheapest_rate_total_amount = serializers.CharField(help_text="Total amount of the cheapest rate")
    cheapest_rate_currency = serializers.CharField(help_text="Billing currency of the cheapest rate")
    cheapest_rate_public_amount = serializers.CharField(help_text="Public display amount")
    cheapest_rate_public_currency = serializers.CharField(help_text="Public display currency")
    cheapest_rate_base_amount = serializers.CharField(help_text="Base amount before taxes/fees")
    cheapest_rate_base_currency = serializers.CharField(help_text="Base currency")
    cheapest_rate_due_at_accommodation_amount = serializers.CharField(
        help_text="Amount due at the property (pay at hotel)"
    )
    cheapest_rate_due_at_accommodation_currency = serializers.CharField(
        help_text="Currency for the amount due at property"
    )

    accommodation = AccommodationSerializer()


class StaySearchResponseSerializer(serializers.Serializer):
    created_at = serializers.DateTimeField(help_text="Timestamp when this search was created")
    results = StayResultSerializer(many=True, help_text="List of matching hotel/stay results")


class StayRatesQuerySerializer(serializers.Serializer):
    search_result_id = serializers.CharField(
        help_text="The 'id' field from a stay search result (e.g. 'srr_0000B5IfJxvta3TIDZa0Ev')"
    )
