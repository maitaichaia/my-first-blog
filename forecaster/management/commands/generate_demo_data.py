"""
Generate demo data for testing the forecasting service without a real Jira connection.

Usage:
    python manage.py generate_demo_data
    python manage.py generate_demo_data --team-name "Backend Team" --sprints 20
"""
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from forecaster.models import Forecast, Issue, Sprint, Team, ThroughputSnapshot


class Command(BaseCommand):
    help = "Generate realistic demo data for testing."

    def add_arguments(self, parser):
        parser.add_argument("--team-name", default="Demo Team")
        parser.add_argument("--board-id", type=int, default=100)
        parser.add_argument("--sprints", type=int, default=16)
        parser.add_argument("--sprint-days", type=int, default=14)

    def handle(self, *args, **options):
        team, _ = Team.objects.update_or_create(
            jira_board_id=options["board_id"],
            defaults={
                "name": options["team_name"],
                "jira_project_key": "DEMO",
            },
        )

        num_sprints = options["sprints"]
        sprint_days = options["sprint_days"]
        base_velocity = random.uniform(25, 45)
        today = date.today()

        sprints_data = []
        for i in range(num_sprints):
            end = today - timedelta(days=i * sprint_days)
            start = end - timedelta(days=sprint_days)
            is_active = i == 0

            committed = round(base_velocity + random.gauss(0, 5), 1)
            noise = random.gauss(0, base_velocity * 0.15)
            completed = max(0, round(committed * random.uniform(0.7, 1.05) + noise, 1))

            sprint = Sprint.objects.update_or_create(
                jira_sprint_id=1000 + i,
                defaults={
                    "team": team,
                    "name": f"Sprint {num_sprints - i}",
                    "state": Sprint.State.ACTIVE if is_active else Sprint.State.CLOSED,
                    "start_date": timezone.make_aware(
                        timezone.datetime(start.year, start.month, start.day)
                    ),
                    "end_date": timezone.make_aware(
                        timezone.datetime(end.year, end.month, end.day)
                    ),
                    "complete_date": None if is_active else timezone.make_aware(
                        timezone.datetime(end.year, end.month, end.day)
                    ),
                    "committed_points": committed,
                    "completed_points": completed,
                    "committed_count": random.randint(8, 18),
                    "completed_count": random.randint(6, 16),
                    "added_during_sprint": random.randint(0, 4),
                    "removed_during_sprint": random.randint(0, 2),
                },
            )[0]
            sprints_data.append(sprint)

        issue_num = 1
        for sprint in sprints_data:
            n_issues = random.randint(8, 16)
            for j in range(n_issues):
                sp = random.choice([1, 2, 3, 5, 8, 3, 5, 2])
                is_done = random.random() < 0.75
                created_dt = sprint.start_date - timedelta(days=random.randint(0, 7))
                resolved_dt = (
                    sprint.start_date + timedelta(days=random.randint(2, 13))
                    if is_done else None
                )
                cycle_h = random.uniform(8, 120) if is_done else None
                lead_h = random.uniform(24, 200) if is_done else None

                Issue.objects.update_or_create(
                    jira_key=f"DEMO-{issue_num}",
                    defaults={
                        "team": team,
                        "sprint": sprint,
                        "summary": f"Demo task #{issue_num}",
                        "issue_type": random.choice(["Story", "Bug", "Task"]),
                        "status": Issue.Status.DONE if is_done else random.choice(
                            [Issue.Status.TODO, Issue.Status.IN_PROGRESS]
                        ),
                        "story_points": sp,
                        "assignee": random.choice(
                            ["Alice", "Bob", "Charlie", "Diana", "Eve"]
                        ),
                        "priority": random.choice(
                            ["Critical", "High", "Medium", "Low"]
                        ),
                        "created_at": created_dt,
                        "resolved_at": resolved_dt,
                        "cycle_time_hours": cycle_h,
                        "lead_time_hours": lead_h,
                    },
                )
                issue_num += 1

        history_days = num_sprints * sprint_days
        for d_offset in range(history_days):
            d = today - timedelta(days=d_offset)
            weekday = d.weekday()
            if weekday >= 5:
                items = random.choices([0, 0, 0, 1], weights=[5, 2, 2, 1])[0]
            else:
                items = max(0, round(random.gauss(1.8, 1.2)))
            points = items * random.uniform(2, 5)
            ThroughputSnapshot.objects.update_or_create(
                team=team,
                date=d,
                defaults={
                    "items_completed": items,
                    "points_completed": round(points, 1),
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Generated demo data: {num_sprints} sprints, "
            f"{issue_num - 1} issues, {history_days} throughput snapshots "
            f"for team '{team.name}'"
        ))
