from django.contrib import admin

from .models import Forecast, Issue, Sprint, Team, ThroughputSnapshot


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "jira_board_id", "jira_project_key", "created_at")


@admin.register(Sprint)
class SprintAdmin(admin.ModelAdmin):
    list_display = (
        "name", "team", "state", "completed_points",
        "committed_points", "start_date", "end_date",
    )
    list_filter = ("team", "state")


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = (
        "jira_key", "summary_short", "team", "status",
        "story_points", "assignee", "resolved_at",
    )
    list_filter = ("team", "status", "issue_type")
    search_fields = ("jira_key", "summary")

    @admin.display(description="Summary")
    def summary_short(self, obj):
        return obj.summary[:80]


@admin.register(ThroughputSnapshot)
class ThroughputSnapshotAdmin(admin.ModelAdmin):
    list_display = ("team", "date", "items_completed", "points_completed")
    list_filter = ("team",)


@admin.register(Forecast)
class ForecastAdmin(admin.ModelAdmin):
    list_display = (
        "team", "target_items", "p85_sprints", "p85_days",
        "avg_throughput_per_sprint", "created_at",
    )
    list_filter = ("team",)
