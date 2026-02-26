"""
Analytics engine — computes velocity, cycle time, throughput metrics
from stored sprint / issue data.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TypedDict

from django.db.models import Avg, Count, F, Q, StdDev, Sum

from .models import Issue, Sprint, Team, ThroughputSnapshot

logger = logging.getLogger(__name__)


class VelocityStats(TypedDict):
    sprint_count: int
    avg_velocity: float
    std_velocity: float
    min_velocity: float
    max_velocity: float
    velocities: list[float]
    avg_completion_rate: float
    trend: str  # "up", "down", "stable"


class CycleTimeStats(TypedDict):
    avg_hours: float
    median_hours: float
    p85_hours: float
    p95_hours: float
    sample_size: int


class ThroughputStats(TypedDict):
    avg_per_day: float
    std_per_day: float
    avg_per_sprint: float
    std_per_sprint: float
    daily_samples: list[int]
    sprint_length_days: int


def get_velocity_stats(
    team: Team, last_n_sprints: int = 12
) -> VelocityStats:
    sprints = (
        Sprint.objects.filter(team=team, state=Sprint.State.CLOSED)
        .order_by("-start_date")[:last_n_sprints]
    )
    velocities = [s.completed_points for s in sprints]
    if not velocities:
        return VelocityStats(
            sprint_count=0,
            avg_velocity=0,
            std_velocity=0,
            min_velocity=0,
            max_velocity=0,
            velocities=[],
            avg_completion_rate=0,
            trend="stable",
        )

    import numpy as np

    v = np.array(velocities)
    rates = [s.completion_rate for s in sprints]

    if len(velocities) >= 4:
        recent = np.mean(v[: len(v) // 2])
        older = np.mean(v[len(v) // 2 :])
        if recent > older * 1.1:
            trend = "up"
        elif recent < older * 0.9:
            trend = "down"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return VelocityStats(
        sprint_count=len(velocities),
        avg_velocity=float(np.mean(v)),
        std_velocity=float(np.std(v, ddof=1)) if len(v) > 1 else 0.0,
        min_velocity=float(np.min(v)),
        max_velocity=float(np.max(v)),
        velocities=velocities,
        avg_completion_rate=float(np.mean(rates)),
        trend=trend,
    )


def get_cycle_time_stats(
    team: Team, days_back: int = 90
) -> CycleTimeStats:
    cutoff = date.today() - timedelta(days=days_back)
    issues = Issue.objects.filter(
        team=team,
        status=Issue.Status.DONE,
        cycle_time_hours__isnull=False,
        resolved_at__date__gte=cutoff,
    ).values_list("cycle_time_hours", flat=True)

    hours_list = list(issues)
    if not hours_list:
        return CycleTimeStats(
            avg_hours=0, median_hours=0, p85_hours=0, p95_hours=0, sample_size=0
        )

    import numpy as np

    h = np.array(hours_list)
    return CycleTimeStats(
        avg_hours=float(np.mean(h)),
        median_hours=float(np.median(h)),
        p85_hours=float(np.percentile(h, 85)),
        p95_hours=float(np.percentile(h, 95)),
        sample_size=len(hours_list),
    )


def get_throughput_stats(
    team: Team, days_back: int = 90, sprint_length_days: int = 14
) -> ThroughputStats:
    cutoff = date.today() - timedelta(days=days_back)
    snapshots = (
        ThroughputSnapshot.objects.filter(team=team, date__gte=cutoff)
        .order_by("date")
        .values_list("items_completed", flat=True)
    )
    daily = list(snapshots)
    if not daily:
        return ThroughputStats(
            avg_per_day=0,
            std_per_day=0,
            avg_per_sprint=0,
            std_per_sprint=0,
            daily_samples=[],
            sprint_length_days=sprint_length_days,
        )

    import numpy as np

    d = np.array(daily, dtype=float)

    sprint_throughputs: list[float] = []
    for i in range(0, len(daily), sprint_length_days):
        chunk = daily[i : i + sprint_length_days]
        if len(chunk) >= sprint_length_days // 2:
            sprint_throughputs.append(sum(chunk))
    s = np.array(sprint_throughputs) if sprint_throughputs else np.array([0.0])

    return ThroughputStats(
        avg_per_day=float(np.mean(d)),
        std_per_day=float(np.std(d, ddof=1)) if len(d) > 1 else 0.0,
        avg_per_sprint=float(np.mean(s)),
        std_per_sprint=float(np.std(s, ddof=1)) if len(s) > 1 else 0.0,
        daily_samples=daily,
        sprint_length_days=sprint_length_days,
    )


def get_team_dashboard_data(team: Team) -> dict:
    """Aggregate all analytics into one payload for the dashboard."""
    velocity = get_velocity_stats(team)
    cycle_time = get_cycle_time_stats(team)
    throughput = get_throughput_stats(team)

    active_sprint = Sprint.objects.filter(
        team=team, state=Sprint.State.ACTIVE
    ).first()
    backlog_count = Issue.objects.filter(
        team=team, status__in=[Issue.Status.TODO, Issue.Status.IN_PROGRESS]
    ).count()

    return {
        "team": {"id": team.id, "name": team.name, "board_id": team.jira_board_id},
        "velocity": velocity,
        "cycle_time": cycle_time,
        "throughput": throughput,
        "active_sprint": {
            "name": active_sprint.name if active_sprint else None,
            "completed_points": active_sprint.completed_points if active_sprint else 0,
            "committed_points": active_sprint.committed_points if active_sprint else 0,
        },
        "backlog_size": backlog_count,
    }
