from rest_framework import serializers

from .models import Forecast, Issue, Sprint, Team, ThroughputSnapshot


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = "__all__"


class SprintSerializer(serializers.ModelSerializer):
    velocity = serializers.FloatField(read_only=True)
    completion_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = Sprint
        fields = [
            "id", "jira_sprint_id", "name", "state",
            "start_date", "end_date", "complete_date",
            "committed_points", "completed_points",
            "committed_count", "completed_count",
            "added_during_sprint", "removed_during_sprint",
            "velocity", "completion_rate", "synced_at",
        ]


class IssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        fields = [
            "id", "jira_key", "summary", "issue_type", "status",
            "story_points", "assignee", "priority",
            "created_at", "resolved_at",
            "cycle_time_hours", "lead_time_hours", "synced_at",
        ]


class ThroughputSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThroughputSnapshot
        fields = ["id", "date", "items_completed", "points_completed"]


class ForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = Forecast
        fields = "__all__"


class ForecastRequestSerializer(serializers.Serializer):
    target_items = serializers.IntegerField(min_value=1)
    sprint_length_days = serializers.IntegerField(min_value=1, default=14)
    history_days = serializers.IntegerField(min_value=14, default=90)
    simulations = serializers.IntegerField(min_value=100, default=10000)


class SprintForecastRequestSerializer(serializers.Serializer):
    target_points = serializers.FloatField(min_value=1)
    history_sprints = serializers.IntegerField(min_value=3, default=12)
    simulations = serializers.IntegerField(min_value=100, default=10000)
