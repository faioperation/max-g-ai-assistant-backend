from django.urls import path
from .views import StaySearchView, StayRatesView

urlpatterns = [
    path("search/", StaySearchView.as_view(), name="stay-search"),
    path("rates/", StayRatesView.as_view(), name="stay-rates"),
]
