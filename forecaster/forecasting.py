"""
Forecasting engine — Monte Carlo simulation for throughput prediction.

Two modes:
  1. Sprint-based: uses historical sprint velocities to predict how many
     sprints are needed to complete N story points.
  2. Throughput-based: uses daily item-completion counts to predict how
     many days / sprints are needed to complete N items.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
from django.conf import settings

from .analytics import get_throughput_stats, get_velocity_stats
from .models import Forecast, Team

logger = logging.getLogger(__name__)


def monte_carlo_sprint_forecast(
    team: Team,
    target_points: float,
    *,
    history_sprints: int | None = None,
    simulations: int | None = None,
) -> dict:
    """
    How many sprints will it take to deliver *target_points* story points?

    Uses bootstrap sampling from historical sprint velocities.
    """
    history_sprints = history_sprints or settings.FORECAST_HISTORY_SPRINTS
    simulations = simulations or settings.FORECAST_SIMULATIONS

    stats = get_velocity_stats(team, last_n_sprints=history_sprints)
    velocities = np.array(stats["velocities"], dtype=float)
    if len(velocities) < 3:
        raise ValueError(
            f"Not enough closed sprints for forecasting ({len(velocities)} < 3). "
            "Sync more sprint data first."
        )

    rng = np.random.default_rng()
    sprints_needed = np.zeros(simulations)

    for i in range(simulations):
        remaining = target_points
        count = 0
        while remaining > 0:
            v = rng.choice(velocities)
            remaining -= v
            count += 1
            if count > 200:
                break
        sprints_needed[i] = count

    percentiles = np.percentile(sprints_needed, [50, 70, 85, 95])

    histogram, bin_edges = np.histogram(
        sprints_needed, bins=range(int(sprints_needed.min()), int(sprints_needed.max()) + 2)
    )

    return {
        "mode": "sprint_velocity",
        "target_points": target_points,
        "simulations": simulations,
        "history_sprints": len(velocities),
        "avg_velocity": stats["avg_velocity"],
        "std_velocity": stats["std_velocity"],
        "p50": float(percentiles[0]),
        "p70": float(percentiles[1]),
        "p85": float(percentiles[2]),
        "p95": float(percentiles[3]),
        "histogram": {
            "bins": [int(b) for b in bin_edges[:-1]],
            "counts": [int(c) for c in histogram],
        },
    }


def monte_carlo_throughput_forecast(
    team: Team,
    target_items: int,
    *,
    sprint_length_days: int = 14,
    history_days: int = 90,
    simulations: int | None = None,
) -> dict:
    """
    How many sprints will it take to deliver *target_items* work items?

    Uses bootstrap sampling from daily throughput data.
    """
    simulations = simulations or settings.FORECAST_SIMULATIONS

    stats = get_throughput_stats(team, days_back=history_days, sprint_length_days=sprint_length_days)
    daily = np.array(stats["daily_samples"], dtype=float)
    if len(daily) < 14:
        raise ValueError(
            f"Not enough daily throughput data ({len(daily)} days < 14). "
            "Sync more data first."
        )

    rng = np.random.default_rng()
    sprints_needed = np.zeros(simulations)

    for i in range(simulations):
        remaining = target_items
        sprint_count = 0
        while remaining > 0:
            days_sample = rng.choice(daily, size=sprint_length_days, replace=True)
            remaining -= days_sample.sum()
            sprint_count += 1
            if sprint_count > 200:
                break
        sprints_needed[i] = sprint_count

    days_needed = sprints_needed * sprint_length_days
    percentiles_sprints = np.percentile(sprints_needed, [50, 70, 85, 95])
    percentiles_days = np.percentile(days_needed, [50, 70, 85, 95])

    histogram, bin_edges = np.histogram(
        sprints_needed,
        bins=range(int(sprints_needed.min()), int(sprints_needed.max()) + 2),
    )

    return {
        "mode": "daily_throughput",
        "target_items": target_items,
        "sprint_length_days": sprint_length_days,
        "simulations": simulations,
        "history_days": len(daily),
        "avg_throughput_per_day": stats["avg_per_day"],
        "avg_throughput_per_sprint": stats["avg_per_sprint"],
        "std_throughput_per_sprint": stats["std_per_sprint"],
        "p50_sprints": float(percentiles_sprints[0]),
        "p70_sprints": float(percentiles_sprints[1]),
        "p85_sprints": float(percentiles_sprints[2]),
        "p95_sprints": float(percentiles_sprints[3]),
        "p50_days": float(percentiles_days[0]),
        "p70_days": float(percentiles_days[1]),
        "p85_days": float(percentiles_days[2]),
        "p95_days": float(percentiles_days[3]),
        "histogram": {
            "bins": [int(b) for b in bin_edges[:-1]],
            "counts": [int(c) for c in histogram],
        },
    }


def run_and_save_forecast(
    team: Team,
    target_items: int,
    sprint_length_days: int = 14,
    history_days: int = 90,
    simulations: int | None = None,
) -> Forecast:
    """Run a Monte Carlo throughput forecast and persist the result."""
    result = monte_carlo_throughput_forecast(
        team,
        target_items,
        sprint_length_days=sprint_length_days,
        history_days=history_days,
        simulations=simulations,
    )
    return Forecast.objects.create(
        team=team,
        target_items=target_items,
        sprint_length_days=sprint_length_days,
        simulations=result["simulations"],
        history_days=result["history_days"],
        p50_sprints=result["p50_sprints"],
        p70_sprints=result["p70_sprints"],
        p85_sprints=result["p85_sprints"],
        p95_sprints=result["p95_sprints"],
        p50_days=result["p50_days"],
        p70_days=result["p70_days"],
        p85_days=result["p85_days"],
        p95_days=result["p95_days"],
        avg_throughput_per_sprint=result["avg_throughput_per_sprint"],
        std_throughput_per_sprint=result["std_throughput_per_sprint"],
        raw_results=result,
    )
