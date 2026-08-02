from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from ..config import ConfigBundle
from ..http import HttpClient
from ..utils import parse_datetime
from .base import CollectedItem

LOGGER = logging.getLogger(__name__)


class GitHubReleaseCollector:
    def __init__(self, config: ConfigBundle, http: HttpClient):
        self.config = config
        self.http = http
        self.source = next((s for s in config.source_list() if s.get("id") == "github_releases"), None)

    def collect(self) -> list[CollectedItem]:
        if not self.source or not self.source.get("enabled"):
            return []
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        result: list[CollectedItem] = []
        for spec in self.source.get("repositories", []):
            if spec.get("enabled", True) is False:
                continue
            repo = spec["repo"]
            url = f"https://api.github.com/repos/{repo}/releases"
            try:
                response = self.http.get(url, headers=headers, params={"per_page": 10})
                if response.status_code == 404:
                    LOGGER.warning("GitHub repo/release endpoint not found: %s", repo)
                    continue
                response.raise_for_status()
            except Exception as exc:
                LOGGER.warning("GitHub release fetch failed %s: %s", repo, exc)
                continue
            for release in response.json():
                published = release.get("published_at") or release.get("created_at")
                dt = parse_datetime(published)
                if dt and dt < cutoff:
                    continue
                result.append(
                    CollectedItem(
                        source_id="github_releases",
                        discovery_source="GitHub Release",
                        source_level="A",
                        discovery_only=False,
                        title=f"{repo} {release.get('name') or release.get('tag_name')}",
                        summary=release.get("body") or "",
                        original_url=release.get("html_url") or "",
                        published_at=published,
                        authors=[(release.get("author") or {}).get("login", "")],
                        external_id=str(release.get("id") or release.get("tag_name") or ""),
                        topic_hint=spec.get("topic", ""),
                        direction_hint=spec.get("direction", ""),
                        priority=20.0,
                        payload={"repo": repo, "tag": release.get("tag_name")},
                    )
                )
        return result
