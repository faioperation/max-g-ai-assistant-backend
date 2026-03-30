from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from .views import api_root_view
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

api_patterns = [
    path("api/v1/", include("api.urls")),
]

schema_view = get_schema_view(
    openapi.Info(
        title="AI Personal Assistant API",
        default_version="v1",
        description="API MAX AI Personal Assistant for backend",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    patterns=api_patterns,
)

urlpatterns = [
    path("", api_root_view),
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    # App APIs
    path("api/v1/", include("api.urls")),
    # Swagger Documentation
    path(
        "docs/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
