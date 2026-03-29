from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from .views import api_root_view
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="AI Personal Assitent API",
        default_version="v1",
        description="API MAX AI Personal Assitent for backend",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("", api_root_view),
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    # App APIs
    path("api/v1/whatsapp/", include("whatsapp.urls")),
    path("api/v1/dashboard/", include("dashboard.urls")),
    path("api/v1/travel/", include("travel.urls")),
    path("api/v1/meeting-schedule/", include("meeting.urls")),
    # Swagger Documentation
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
