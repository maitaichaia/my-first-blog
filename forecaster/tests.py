import random
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .analytics import get_cycle_time_stats, get_throughput_stats, get_velocity_stats
from .forecasting import monte_carlo_sprint_forecast, monte_carlo_throughput_forecast
from .models import Forecast, Issue, Sprint, Team, ThroughputSnapshot


def _create_test_team():
    return Team.objects.create(
        name="Test Team", jira_board_id=999, jira_project_key="TEST"
    )


def _populate_sprints(team, n=10, base_velocity=30.0):
    sprints = []
    for i in range(n):
        end = timezone.now() - timedelta(days=i * 14)
        start = end - timedelta(days=14)
        committed = base_velocity + random.gauss(0, 3)
        completed = committed * random.uniform(0.7, 1.0)
        s = Sprint.objects.create(
            team=team,
            jira_sprint_id=2000 + i,
            name=f"Sprint {n - i}",
            state=Sprint.State.CLOSED,
            start_date=start,
            end_date=end,
            complete_date=end,
            committed_points=round(committed, 1),
            completed_points=round(completed, 1),
            committed_count=random.randint(8, 15),
            completed_count=random.randint(6, 13),
        )
        sprints.append(s)
    return sprints


def _populate_throughput(team, days=90):
    today = date.today()
    for i in range(days):
        d = today - timedelta(days=i)
        ThroughputSnapshot.objects.create(
            team=team,
            date=d,
            items_completed=max(0, round(random.gauss(2, 1.5))),
            points_completed=round(random.uniform(0, 10), 1),
        )


def _populate_issues(team, sprints):
    for sprint in sprints:
        for j in range(8):
            is_done = random.random() < 0.75
            created_dt = sprint.start_date - timedelta(days=random.randint(0, 5))
            resolved_dt = sprint.start_date + timedelta(days=random.randint(2, 12)) if is_done else None
            Issue.objects.create(
                team=team,
                sprint=sprint,
                jira_key=f"TEST-{sprint.jira_sprint_id}-{j}",
                summary=f"Test issue {j}",
                issue_type="Story",
                status=Issue.Status.DONE if is_done else Issue.Status.TODO,
                story_points=random.choice([1, 2, 3, 5, 8]),
                cycle_time_hours=random.uniform(8, 100) if is_done else None,
                lead_time_hours=random.uniform(24, 200) if is_done else None,
                created_at=created_dt,
                resolved_at=resolved_dt,
            )


class ModelTests(TestCase):
    def test_sprint_velocity_and_completion(self):
        team = _create_test_team()
        s = Sprint.objects.create(
            team=team, jira_sprint_id=1, name="S1",
            state=Sprint.State.CLOSED,
            committed_points=30, completed_points=24,
        )
        self.assertEqual(s.velocity, 24)
        self.assertAlmostEqual(s.completion_rate, 0.8)

    def test_sprint_zero_committed(self):
        team = _create_test_team()
        s = Sprint.objects.create(
            team=team, jira_sprint_id=2, name="S2",
            state=Sprint.State.CLOSED,
            committed_points=0, completed_points=0,
        )
        self.assertEqual(s.completion_rate, 0.0)


class AnalyticsTests(TestCase):
    def setUp(self):
        self.team = _create_test_team()
        self.sprints = _populate_sprints(self.team, n=10)
        _populate_throughput(self.team, days=90)
        _populate_issues(self.team, self.sprints)

    def test_velocity_stats(self):
        stats = get_velocity_stats(self.team, last_n_sprints=10)
        self.assertEqual(stats["sprint_count"], 10)
        self.assertGreater(stats["avg_velocity"], 0)
        self.assertIn(stats["trend"], ("up", "down", "stable"))

    def test_cycle_time_stats(self):
        stats = get_cycle_time_stats(self.team, days_back=365)
        self.assertGreater(stats["sample_size"], 0)
        self.assertGreater(stats["avg_hours"], 0)

    def test_throughput_stats(self):
        stats = get_throughput_stats(self.team, days_back=90)
        self.assertGreater(stats["avg_per_day"], 0)
        self.assertGreater(len(stats["daily_samples"]), 0)


class ForecastTests(TestCase):
    def setUp(self):
        self.team = _create_test_team()
        _populate_sprints(self.team, n=10, base_velocity=30)
        _populate_throughput(self.team, days=90)

    def test_sprint_forecast(self):
        result = monte_carlo_sprint_forecast(
            self.team, target_points=60, simulations=1000
        )
        self.assertIn("p85", result)
        self.assertGreater(result["p85"], 0)
        self.assertEqual(result["mode"], "sprint_velocity")

    def test_throughput_forecast(self):
        result = monte_carlo_throughput_forecast(
            self.team, target_items=20, simulations=1000, history_days=90
        )
        self.assertIn("p85_sprints", result)
        self.assertGreater(result["p85_sprints"], 0)
        self.assertEqual(result["mode"], "daily_throughput")


class APITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.team = _create_test_team()
        self.sprints = _populate_sprints(self.team, n=10)
        _populate_throughput(self.team, days=90)
        _populate_issues(self.team, self.sprints)

    def test_team_list(self):
        resp = self.client.get("/api/teams/")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard(self):
        resp = self.client.get(f"/api/teams/{self.team.id}/dashboard/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("velocity", data)
        self.assertIn("cycle_time", data)
        self.assertIn("throughput", data)

    def test_velocity_endpoint(self):
        resp = self.client.get(f"/api/teams/{self.team.id}/velocity/")
        self.assertEqual(resp.status_code, 200)

    def test_sprint_list(self):
        resp = self.client.get(f"/api/sprints/?team={self.team.id}")
        self.assertEqual(resp.status_code, 200)

    def test_issue_list(self):
        resp = self.client.get(f"/api/issues/?team={self.team.id}")
        self.assertEqual(resp.status_code, 200)

    def test_throughput_forecast(self):
        resp = self.client.post(
            f"/api/teams/{self.team.id}/forecast/throughput/",
            {"target_items": 20, "sprint_length_days": 14, "history_days": 90, "simulations": 500},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("p85_sprints", data)

    def test_sprint_forecast(self):
        resp = self.client.post(
            f"/api/teams/{self.team.id}/forecast/sprint/",
            {"target_points": 60, "history_sprints": 10, "simulations": 500},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("p85", data)

    def test_dashboard_page(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Throughput")
