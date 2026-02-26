"""
Data synchronization service — pulls data from Jira and persists it locally.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date

from django.utils import timezone

from .jira_client import JiraClient
from .models import Issue, Sprint, Team, ThroughputSnapshot

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "To Do": Issue.Status.TODO,
    "Open": Issue.Status.TODO,
    "Backlog": Issue.Status.TODO,
    "In Progress": Issue.Status.IN_PROGRESS,
    "In Development": Issue.Status.IN_PROGRESS,
    "In Review": Issue.Status.IN_REVIEW,
    "Code Review": Issue.Status.IN_REVIEW,
    "Done": Issue.Status.DONE,
    "Closed": Issue.Status.DONE,
    "Resolved": Issue.Status.DONE,
}


def sync_team_sprints(team: Team, client: JiraClient | None = None) -> int:
    """Sync all sprints for a team's board. Returns count of synced sprints."""
    client = client or JiraClient()
    raw_sprints = client.get_sprints(team.jira_board_id)
    count = 0

    for raw in raw_sprints:
        sprint, created = Sprint.objects.update_or_create(
            jira_sprint_id=raw["id"],
            defaults={
                "team": team,
                "name": raw.get("name", ""),
                "state": raw.get("state", "future"),
                "start_date": client.parse_datetime(raw.get("startDate")),
                "end_date": client.parse_datetime(raw.get("endDate")),
                "complete_date": client.parse_datetime(raw.get("completeDate")),
            },
        )

        if sprint.state == Sprint.State.CLOSED:
            _sync_sprint_metrics(team, sprint, client)

        count += 1

    logger.info("Synced %d sprints for team %s", count, team.name)
    return count


def _sync_sprint_metrics(team: Team, sprint: Sprint, client: JiraClient):
    """Pull sprint report and compute committed / completed metrics."""
    try:
        report = client.get_sprint_report(team.jira_board_id, sprint.jira_sprint_id)
        contents = report.get("contents", {})

        completed = contents.get("completedIssues", [])
        not_completed = contents.get("issuesNotCompletedInCurrentSprint", [])
        added = contents.get("issuesAddedDuringSprint", {})
        removed = contents.get("puntedIssues", [])

        def _points(items):
            total = 0.0
            for item in items:
                sp = item.get("estimateStatistic", {}).get(
                    "statFieldValue", {}
                ).get("value")
                if sp:
                    total += float(sp)
            return total

        sprint.completed_points = _points(completed)
        sprint.completed_count = len(completed)
        sprint.committed_points = _points(completed) + _points(not_completed)
        sprint.committed_count = len(completed) + len(not_completed)
        sprint.added_during_sprint = len(added) if isinstance(added, list) else 0
        sprint.removed_during_sprint = len(removed)
        sprint.save()
    except Exception:
        logger.exception("Failed to sync sprint report for %s", sprint.name)


def sync_team_issues(
    team: Team, jql_extra: str = "", client: JiraClient | None = None
) -> int:
    """Sync issues from Jira for the team's project. Returns count."""
    client = client or JiraClient()
    jql = f'project = "{team.jira_project_key}" ORDER BY created DESC'
    if jql_extra:
        jql = f'project = "{team.jira_project_key}" AND {jql_extra} ORDER BY created DESC'

    raw_issues = client.search_issues(
        jql,
        fields="summary,status,issuetype,story_points,customfield_10028,"
               "assignee,priority,created,resolutiondate",
    )
    count = 0

    for raw in raw_issues:
        fields = raw.get("fields", {})
        status_name = fields.get("status", {}).get("name", "")
        mapped_status = STATUS_MAP.get(status_name, Issue.Status.TODO)

        sp = fields.get("story_points") or fields.get("customfield_10028")

        created_dt = client.parse_datetime(fields.get("created"))
        resolved_dt = client.parse_datetime(fields.get("resolutiondate"))

        cycle_time = None
        lead_time = None
        if created_dt and resolved_dt:
            lead_time = (resolved_dt - created_dt).total_seconds() / 3600

        assignee_data = fields.get("assignee") or {}
        assignee_name = assignee_data.get("displayName", "")

        Issue.objects.update_or_create(
            jira_key=raw["key"],
            defaults={
                "team": team,
                "summary": (fields.get("summary") or "")[:500],
                "issue_type": fields.get("issuetype", {}).get("name", ""),
                "status": mapped_status,
                "story_points": float(sp) if sp else None,
                "assignee": assignee_name,
                "priority": fields.get("priority", {}).get("name", ""),
                "created_at": created_dt,
                "resolved_at": resolved_dt,
                "lead_time_hours": lead_time,
                "cycle_time_hours": cycle_time,
            },
        )
        count += 1

    logger.info("Synced %d issues for team %s", count, team.name)
    return count


def build_throughput_snapshots(team: Team, days_back: int = 180) -> int:
    """
    Build daily throughput snapshots from resolved issue dates.
    """
    cutoff = date.today() - __import__("datetime").timedelta(days=days_back)
    issues = Issue.objects.filter(
        team=team, status=Issue.Status.DONE, resolved_at__isnull=False,
        resolved_at__date__gte=cutoff,
    )

    daily: dict[date, dict] = defaultdict(lambda: {"items": 0, "points": 0.0})
    for issue in issues:
        d = issue.resolved_at.date()
        daily[d]["items"] += 1
        daily[d]["points"] += issue.story_points or 0

    count = 0
    for d, vals in daily.items():
        ThroughputSnapshot.objects.update_or_create(
            team=team,
            date=d,
            defaults={
                "items_completed": vals["items"],
                "points_completed": vals["points"],
            },
        )
        count += 1

    current = cutoff
    while current <= date.today():
        if current not in daily:
            ThroughputSnapshot.objects.update_or_create(
                team=team, date=current, defaults={"items_completed": 0, "points_completed": 0}
            )
            count += 1
        current += __import__("datetime").timedelta(days=1)

    logger.info("Built %d throughput snapshots for team %s", count, team.name)
    return count


def full_sync(team: Team) -> dict:
    """Full sync: sprints, issues, throughput snapshots."""
    client = JiraClient()
    sprints_count = sync_team_sprints(team, client)
    issues_count = sync_team_issues(team, client=client)
    snapshots_count = build_throughput_snapshots(team)
    return {
        "sprints_synced": sprints_count,
        "issues_synced": issues_count,
        "snapshots_built": snapshots_count,
    }
