"""
Jira Cloud REST API client.

Supports:
  - Fetching boards, sprints, sprint reports
  - Fetching issues with changelog for cycle-time calculations
  - Pagination handling
"""
import logging
from datetime import datetime
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class JiraClientError(Exception):
    pass


class JiraClient:
    """Thin wrapper around the Jira Cloud REST API (v2 + Agile)."""

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ):
        self.base_url = (base_url or settings.JIRA_BASE_URL).rstrip("/")
        self.auth = (
            email or settings.JIRA_USER_EMAIL,
            api_token or settings.JIRA_API_TOKEN,
        )
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({"Accept": "application/json"})

    def _get(self, url: str, params: dict | None = None) -> dict:
        resp = self.session.get(url, params=params, timeout=30)
        if resp.status_code >= 400:
            logger.error("Jira API error %s: %s", resp.status_code, resp.text[:500])
            raise JiraClientError(
                f"Jira API returned {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json()

    def _get_paginated(
        self, url: str, results_key: str = "values", params: dict | None = None
    ) -> list[dict]:
        params = dict(params or {})
        params.setdefault("maxResults", 50)
        all_results: list[dict] = []
        start = 0
        while True:
            params["startAt"] = start
            data = self._get(url, params)
            items = data.get(results_key, [])
            all_results.extend(items)
            if data.get("isLast", True) or len(items) == 0:
                break
            start += len(items)
        return all_results

    # ── Boards ───────────────────────────────────────────────────────

    def get_boards(self, project_key: str | None = None) -> list[dict]:
        url = f"{self.base_url}/rest/agile/1.0/board"
        params = {}
        if project_key:
            params["projectKeyOrId"] = project_key
        return self._get_paginated(url, params=params)

    def get_board(self, board_id: int) -> dict:
        return self._get(f"{self.base_url}/rest/agile/1.0/board/{board_id}")

    # ── Sprints ──────────────────────────────────────────────────────

    def get_sprints(
        self, board_id: int, state: str | None = None
    ) -> list[dict]:
        url = f"{self.base_url}/rest/agile/1.0/board/{board_id}/sprint"
        params = {}
        if state:
            params["state"] = state
        return self._get_paginated(url, params=params)

    def get_sprint(self, sprint_id: int) -> dict:
        return self._get(f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}")

    def get_sprint_issues(self, sprint_id: int) -> list[dict]:
        url = f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}/issue"
        return self._get_paginated(url, results_key="issues", params={
            "fields": "summary,status,issuetype,story_points,customfield_10028,"
                      "assignee,priority,created,resolutiondate",
            "maxResults": 100,
        })

    def get_sprint_report(self, board_id: int, sprint_id: int) -> dict:
        """Greenhopper sprint report — gives committed/completed breakdown."""
        url = (
            f"{self.base_url}/rest/greenhopper/1.0/rapid/charts/sprintreport"
        )
        return self._get(url, params={"rapidViewId": board_id, "sprintId": sprint_id})

    # ── Issues ───────────────────────────────────────────────────────

    def search_issues(self, jql: str, fields: str | None = None, expand: str | None = None) -> list[dict]:
        url = f"{self.base_url}/rest/api/2/search"
        params: dict[str, Any] = {"jql": jql, "maxResults": 100}
        if fields:
            params["fields"] = fields
        if expand:
            params["expand"] = expand
        return self._get_paginated(url, results_key="issues", params=params)

    def get_issue_changelog(self, issue_key: str) -> list[dict]:
        url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
        data = self._get(url, params={"expand": "changelog"})
        return data.get("changelog", {}).get("histories", [])

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None
