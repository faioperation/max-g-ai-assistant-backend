from rest_framework import serializers

class StayGuestSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=["adult", "child"],
        default="adult"
    )

class StaySearchSerializer(serializers.Serializer):
    location_name = serializers.CharField(
        help_text="Name of the city or area to search in (e.g. Dhaka, New York)"
    )
    check_in_date = serializers.DateField(
        help_text="Check-in date in YYYY-MM-DD format"
    )
    check_out_date = serializers.DateField(
        help_text="Check-out date in YYYY-MM-DD format"
    )
    guests = StayGuestSerializer(
        many=True,
        default=[{"type": "adult"}]
    )
    rooms = serializers.IntegerField(
        default=1,
        min_value=1
    )
    radius = serializers.IntegerField(
        default=10,
        help_text="Search radius in kilometers"
    )
