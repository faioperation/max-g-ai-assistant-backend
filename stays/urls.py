from django.urls import path
from stays.views import (
    StaySearchView,
    StayRatesView,
    StayHoldView,
    StayPaymentCheckoutView,
    StayPaymentSuccessAPIView,
)

urlpatterns = [
    path("search/", StaySearchView.as_view(), name="stay-search"),
    path("rates/", StayRatesView.as_view(), name="stay-rates"),
    path("hold/", StayHoldView.as_view(), name="stay-hold"),
    path(
        "checkout/<str:intent_id>/",
        StayPaymentCheckoutView.as_view(),
        name="stay-checkout",
    ),
    path(
        "api/payment/success/",
        StayPaymentSuccessAPIView.as_view(),
        name="stay-payment-success",
    ),
]
