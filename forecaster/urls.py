from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"teams", views.TeamViewSet, basename="team")
router.register(r"sprints", views.SprintViewSet, basename="sprint")
router.register(r"issues", views.IssueViewSet, basename="issue")
router.register(r"throughput", views.ThroughputSnapshotViewSet, basename="throughput-snapshot")
router.register(r"forecasts", views.ForecastViewSet, basename="forecast")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "teams/<int:team_id>/forecast/throughput/",
        views.ThroughputForecastView.as_view(),
        name="forecast-throughput",
    ),
    path(
        "teams/<int:team_id>/forecast/sprint/",
        views.SprintForecastView.as_view(),
        name="forecast-sprint",
    ),
]
