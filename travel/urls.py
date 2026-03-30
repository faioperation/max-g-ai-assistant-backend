from django.urls import path
from travel.views import FlightSearchView, FlightBookView

urlpatterns = [
    path("flights/search/", FlightSearchView.as_view(), name="flight-search"),
    path("flights/book/", FlightBookView.as_view(), name="flight-book"),
]
