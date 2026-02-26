"""
Management command to sync Jira data.

Usage:
    python manage.py sync_jira                  # sync all teams
    python manage.py sync_jira --team-id 1      # sync specific team
"""
from django.core.management.base import BaseCommand, CommandError

from forecaster.models import Team
from forecaster.sync import full_sync


class Command(BaseCommand):
    help = "Synchronize sprint/issue data from Jira for all (or a specific) team."

    def add_arguments(self, parser):
        parser.add_argument(
            "--team-id", type=int, help="Sync only this team (by DB id)"
        )

    def handle(self, *args, **options):
        team_id = options.get("team_id")
        teams = Team.objects.filter(pk=team_id) if team_id else Team.objects.all()

        if not teams.exists():
            raise CommandError("No teams found. Create a team first.")

        for team in teams:
            self.stdout.write(f"Syncing team: {team.name} (board {team.jira_board_id})...")
            try:
                result = full_sync(team)
                self.stdout.write(self.style.SUCCESS(
                    f"  Done — {result['sprints_synced']} sprints, "
                    f"{result['issues_synced']} issues, "
                    f"{result['snapshots_built']} snapshots"
                ))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  Error: {e}"))
