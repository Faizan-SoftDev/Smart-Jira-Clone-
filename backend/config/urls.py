"""Root URL routing kept intentionally small while domain APIs are added."""

from django.http import JsonResponse
from django.db import connection
from django.urls import include, path
from apps.core import views as core_views


def health_check(request):
    """Return a lightweight liveness response without accessing application data."""
    return JsonResponse({"status": "ok", "service": "taskcraft"})


def readiness_check(request):
    """Confirm the application can reach its primary datastore."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable", "service": "taskcraft"}, status=503)
    return JsonResponse({"status": "ready", "service": "taskcraft"})


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("ready/", readiness_check, name="readiness-check"),
    path("privacy/", core_views.privacy_policy, name="privacy-policy"),
    path("terms/", core_views.terms_of_service, name="terms-of-service"),
    path("refunds/", core_views.refund_policy, name="refund-policy"),
    path("robots.txt", core_views.robots_txt, name="robots-txt"),
    path("sitemap.xml", core_views.sitemap_xml, name="sitemap-xml"),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.billing.urls")),
    path("api/v1/", include("apps.workspaces.urls")),
    path("api/v1/", include("apps.projects.urls")),
    path("api/v1/", include("apps.issues.urls")),
]
