from django.urls import path
from travel.views import (
    FlightSearchView,
    FlightHoldView,
    PaymentCheckoutView,
    PaymentSuccessAPIView,
)

urlpatterns = [
    path("flights/search/", FlightSearchView.as_view(), name="flight-search"),
    path("flights/hold/", FlightHoldView.as_view(), name="flight-hold"),
    path(
        "checkout/<str:intent_id>/", PaymentCheckoutView.as_view(), name="checkout_page"
    ),
    path(
        "api/payment/success/", PaymentSuccessAPIView.as_view(), name="payment-success"
    ),
]
