from django.db import models


class Team(models.Model):
    name = models.CharField(max_length=200, unique=True)
    jira_board_id = models.IntegerField(unique=True)
    jira_project_key = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Sprint(models.Model):
    class State(models.TextChoices):
        ACTIVE = "active"
        CLOSED = "closed"
        FUTURE = "future"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="sprints")
    jira_sprint_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=300)
    state = models.CharField(max_length=10, choices=State.choices)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    complete_date = models.DateTimeField(null=True, blank=True)

    committed_points = models.FloatField(default=0)
    completed_points = models.FloatField(default=0)
    committed_count = models.IntegerField(default=0)
    completed_count = models.IntegerField(default=0)
    added_during_sprint = models.IntegerField(default=0)
    removed_during_sprint = models.IntegerField(default=0)

    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} ({self.state})"

    @property
    def velocity(self):
        return self.completed_points

    @property
    def completion_rate(self):
        if self.committed_points == 0:
            return 0.0
        return self.completed_points / self.committed_points


class Issue(models.Model):
    class Status(models.TextChoices):
        TODO = "todo"
        IN_PROGRESS = "in_progress"
        IN_REVIEW = "in_review"
        DONE = "done"

    sprint = models.ForeignKey(
        Sprint, on_delete=models.CASCADE, related_name="issues", null=True, blank=True
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="issues")
    jira_key = models.CharField(max_length=50, unique=True)
    summary = models.CharField(max_length=500)
    issue_type = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    story_points = models.FloatField(null=True, blank=True)
    assignee = models.CharField(max_length=200, blank=True)
    priority = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    cycle_time_hours = models.FloatField(null=True, blank=True)
    lead_time_hours = models.FloatField(null=True, blank=True)

    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.jira_key}: {self.summary[:60]}"


class ThroughputSnapshot(models.Model):
    """Daily throughput snapshot — how many items were completed each day."""
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="throughput_snapshots"
    )
    date = models.DateField()
    items_completed = models.IntegerField(default=0)
    points_completed = models.FloatField(default=0)

    class Meta:
        ordering = ["-date"]
        unique_together = ("team", "date")

    def __str__(self):
        return f"{self.team.name} | {self.date} | {self.items_completed} items"


class Forecast(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="forecasts")
    created_at = models.DateTimeField(auto_now_add=True)

    target_items = models.IntegerField(help_text="Number of items to forecast completion for")
    sprint_length_days = models.IntegerField(default=14)
    simulations = models.IntegerField(default=10000)
    history_days = models.IntegerField(default=90)

    p50_sprints = models.FloatField(help_text="50th percentile — sprints needed")
    p70_sprints = models.FloatField(help_text="70th percentile")
    p85_sprints = models.FloatField(help_text="85th percentile")
    p95_sprints = models.FloatField(help_text="95th percentile")

    p50_days = models.FloatField()
    p70_days = models.FloatField()
    p85_days = models.FloatField()
    p95_days = models.FloatField()

    avg_throughput_per_sprint = models.FloatField()
    std_throughput_per_sprint = models.FloatField()

    raw_results = models.JSONField(
        default=dict,
        help_text="Full simulation histogram data",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Forecast for {self.team.name}: {self.target_items} items "
            f"(p85={self.p85_sprints:.1f} sprints)"
        )
