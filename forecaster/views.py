from rest_framework import generics, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from .analytics import (
    get_cycle_time_stats,
    get_team_dashboard_data,
    get_throughput_stats,
    get_velocity_stats,
)
from .forecasting import (
    monte_carlo_sprint_forecast,
    monte_carlo_throughput_forecast,
    run_and_save_forecast,
)
from .models import Forecast, Issue, Sprint, Team, ThroughputSnapshot
from .serializers import (
    ForecastRequestSerializer,
    ForecastSerializer,
    IssueSerializer,
    SprintForecastRequestSerializer,
    SprintSerializer,
    TeamSerializer,
    ThroughputSnapshotSerializer,
)
from .sync import full_sync


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        team = self.get_object()
        try:
            result = full_sync(team)
            return Response({"status": "ok", **result})
        except Exception as e:
            return Response(
                {"status": "error", "detail": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    @action(detail=True, methods=["get"])
    def dashboard(self, request, pk=None):
        team = self.get_object()
        data = get_team_dashboard_data(team)
        return Response(data)

    @action(detail=True, methods=["get"])
    def velocity(self, request, pk=None):
        team = self.get_object()
        n = int(request.query_params.get("sprints", 12))
        return Response(get_velocity_stats(team, last_n_sprints=n))

    @action(detail=True, methods=["get"])
    def cycle_time(self, request, pk=None):
        team = self.get_object()
        days = int(request.query_params.get("days", 90))
        return Response(get_cycle_time_stats(team, days_back=days))

    @action(detail=True, methods=["get"])
    def throughput(self, request, pk=None):
        team = self.get_object()
        days = int(request.query_params.get("days", 90))
        sprint_len = int(request.query_params.get("sprint_length", 14))
        return Response(get_throughput_stats(team, days_back=days, sprint_length_days=sprint_len))


class SprintViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SprintSerializer

    def get_queryset(self):
        qs = Sprint.objects.all()
        team_id = self.request.query_params.get("team")
        if team_id:
            qs = qs.filter(team_id=team_id)
        state = self.request.query_params.get("state")
        if state:
            qs = qs.filter(state=state)
        return qs


class IssueViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IssueSerializer

    def get_queryset(self):
        qs = Issue.objects.all()
        team_id = self.request.query_params.get("team")
        if team_id:
            qs = qs.filter(team_id=team_id)
        sprint_id = self.request.query_params.get("sprint")
        if sprint_id:
            qs = qs.filter(sprint_id=sprint_id)
        issue_status = self.request.query_params.get("status")
        if issue_status:
            qs = qs.filter(status=issue_status)
        return qs


class ThroughputSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ThroughputSnapshotSerializer

    def get_queryset(self):
        qs = ThroughputSnapshot.objects.all()
        team_id = self.request.query_params.get("team")
        if team_id:
            qs = qs.filter(team_id=team_id)
        return qs


class ForecastViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ForecastSerializer

    def get_queryset(self):
        qs = Forecast.objects.all()
        team_id = self.request.query_params.get("team")
        if team_id:
            qs = qs.filter(team_id=team_id)
        return qs


class ThroughputForecastView(APIView):
    """
    POST /api/teams/{team_id}/forecast/throughput/
    Runs a Monte Carlo simulation based on daily throughput data.
    """

    def post(self, request, team_id):
        team = Team.objects.get(pk=team_id)
        ser = ForecastRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            forecast = run_and_save_forecast(
                team,
                target_items=ser.validated_data["target_items"],
                sprint_length_days=ser.validated_data["sprint_length_days"],
                history_days=ser.validated_data["history_days"],
                simulations=ser.validated_data["simulations"],
            )
            return Response(ForecastSerializer(forecast).data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SprintForecastView(APIView):
    """
    POST /api/teams/{team_id}/forecast/sprint/
    Runs a Monte Carlo simulation based on sprint velocities.
    """

    def post(self, request, team_id):
        team = Team.objects.get(pk=team_id)
        ser = SprintForecastRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            result = monte_carlo_sprint_forecast(
                team,
                target_points=ser.validated_data["target_points"],
                history_sprints=ser.validated_data["history_sprints"],
                simulations=ser.validated_data["simulations"],
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
