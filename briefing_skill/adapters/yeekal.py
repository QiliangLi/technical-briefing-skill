from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from ..config import ConfigBundle
from ..db import Database
from ..feed import parse_feed
from ..http import HttpClient
from ..source_metadata import extract_published_at
from ..utils import canonicalize_url, complete_sentence_excerpt, normalize_text, now_iso, stable_hash, tokenize
from .base import CollectedItem

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class IssuePage:
    url: str
    discovered_at: str | None


class YeeKalDailyCollector:
    """Resolve YeeKal daily issues into external discovery links."""

    def __init__(self, config: ConfigBundle, db: Database, http: HttpClient):
        self.config = config
        self.db = db
        self.http = http
        self.source = next(
            (source for source in config.source_list() if source.get("type") == "yeekal_daily"),
            None,
        )
        self._terms_by_topic = self._technical_terms()

    def collect(self) -> list[CollectedItem]:
        if not self.source or not self.source.get("enabled", True):
            return []
        issues = self._rss_issues()
        if issues is None:
            issues = self._index_issues()
        if not issues:
            return []
        result: list[CollectedItem] = []
        seen: set[str] = set()
        for issue in issues[: int(self.source.get("max_issue_pages", 3))]:
            try:
                issue_html = self._etag_text(f"yeekal:issue:{issue.url}", issue.url)
                if issue_html is None:
                    continue
                links = self._external_links(issue_html, issue)
            except Exception as exc:
                LOGGER.warning("YeeKal issue failed %s: %s", issue.url, exc)
                continue
            for link in links[: int(self.source.get("max_external_links_per_issue", 40))]:
                canonical = canonicalize_url(link["url"])
                if not canonical or canonical in seen:
                    continue
                matched_topics = self._matching_topics(
                    f"{link['title']} {link['summary']} {link['section']}"
                )
                if not matched_topics:
                    continue
                seen.add(canonical)
                published_at = None
                try:
                    response = self.http.get(canonical)
                    response.raise_for_status()
                    published_at = extract_published_at(response.text, canonical)
                except Exception as exc:
                    LOGGER.debug("YeeKal source metadata unavailable %s: %s", canonical, exc)
                topic_hint = max(
                    matched_topics,
                    key=lambda topic_id: float((self.source.get("topic_boosts") or {}).get(topic_id, 1.0)),
                )
                boost = float((self.source.get("topic_boosts") or {}).get(topic_hint, 1.0))
                result.append(
                    CollectedItem(
                        source_id="yeekal_daily",
                        discovery_source="YeeKal AI Daily",
                        source_level="B",
                        discovery_only=True,
                        title=link["title"],
                        summary=link["summary"],
                        original_url=canonical,
                        published_at=published_at,
                        discovered_at=issue.discovered_at,
                        external_id=stable_hash(issue.url, canonical),
                        topic_hint=topic_hint,
                        priority=float(self.source.get("base_priority", 14)) * boost,
                        payload={
                            "issue_url": issue.url,
                            "section": link["section"],
                            "link_text": link["link_text"],
                            "matched_topics": sorted(matched_topics),
                            "source_role": "aggregated_discovery",
                        },
                    )
                )
        return result

    def _rss_issues(self) -> list[IssuePage] | None:
        url = str(self.source.get("rss_url") or "")
        if not url:
            return None
        try:
            text = self._etag_text(f"yeekal:rss:{url}", url)
            if text is None:
                return []
            return [
                IssuePage(url=entry.link, discovered_at=entry.published or entry.updated)
                for entry in parse_feed(text)
                if entry.link
            ]
        except Exception as exc:
            LOGGER.warning("YeeKal RSS failed, falling back to index: %s", exc)
            return None

    def _index_issues(self) -> list[IssuePage]:
        url = str(self.source.get("index_url") or "")
        if not url:
            return []
        try:
            text = self._etag_text(f"yeekal:index:{url}", url)
            if text is None:
                return []
        except Exception as exc:
            LOGGER.warning("YeeKal index failed: %s", exc)
            return []
        soup = BeautifulSoup(text, "html.parser")
        issues: list[IssuePage] = []
        seen: set[str] = set()
        index_url = canonicalize_url(url)
        for anchor in soup.find_all("a", href=True):
            issue_url = canonicalize_url(urljoin(url, str(anchor.get("href"))))
            if not issue_url or issue_url == index_url or issue_url in seen or not self._is_issue_url(issue_url):
                continue
            seen.add(issue_url)
            issues.append(IssuePage(issue_url, self._date_from_text(anchor.get_text(" ", strip=True)) or now_iso()))
        return issues

    def _etag_text(self, state_key: str, url: str) -> str | None:
        state = self.db.get_source_state(state_key) or {}
        headers = {"If-None-Match": state["etag"]} if state.get("etag") else None
        response = self.http.get(url, headers=headers)
        if response.status_code == 304:
            return None
        response.raise_for_status()
        self.db.upsert_source_state(state_key, etag=response.headers.get("ETag"), payload={"url": url})
        return response.text

    @staticmethod
    def _is_issue_url(url: str) -> bool:
        parts = urlsplit(url)
        return (parts.hostname or "").lower().endswith("yeekal.com") and bool(
            re.search(r"/daily/.+", parts.path.rstrip("/"))
        )

    @staticmethod
    def _date_from_text(text: str) -> str | None:
        match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text or "")
        if not match:
            return None
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}T00:00:00+00:00"

    def _external_links(self, html: str, issue: IssuePage) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("article") or soup.find("main") or soup.body or soup
        links: list[dict[str, str]] = []
        seen: set[str] = set()
        for anchor in main.find_all("a", href=True):
            url = canonicalize_url(urljoin(issue.url, str(anchor.get("href"))))
            if not self._external_candidate(url, anchor):
                continue
            if url in seen:
                continue
            seen.add(url)
            link_text = " ".join(anchor.get_text(" ", strip=True).split())
            heading = self._nearest_heading(anchor)
            container = anchor.find_parent(["article", "section", "li", "div", "p"])
            if container is None or container is main:
                context = link_text
            else:
                context = " ".join(container.get_text(" ", strip=True).split())
            summary = complete_sentence_excerpt(context, 280)
            title = link_text or heading
            if not title:
                continue
            links.append(
                {
                    "url": url,
                    "title": complete_sentence_excerpt(title, 160),
                    "summary": summary,
                    "section": heading,
                    "link_text": link_text,
                }
            )
        return links

    @staticmethod
    def _nearest_heading(anchor: Tag) -> str:
        previous = anchor.find_previous(["h1", "h2", "h3", "h4", "h5"])
        return " ".join(previous.get_text(" ", strip=True).split()) if previous else ""

    @staticmethod
    def _external_candidate(url: str, anchor: Tag) -> bool:
        if not url or url.startswith(("mailto:", "javascript:")):
            return False
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if not host or host == "yeekal.com" or host.endswith(".yeekal.com"):
            return False
        if re.search(r"\.(?:png|jpe?g|gif|svg|webp|ico|mp4|mp3|zip)(?:$|\?)", parts.path, flags=re.I):
            return False
        text = " ".join(anchor.get_text(" ", strip=True).split())
        if not text and anchor.find("img"):
            return False
        lowered = text.lower()
        if lowered in {"share", "分享", "twitter", "x", "github"} and len(parts.path.strip("/")) == 0:
            return False
        return True

    def _technical_terms(self) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for topic in self.config.topic_list():
            terms: set[str] = set()
            for direction in topic.get("directions", []):
                for key in ("include_terms", "aihot_boost_terms"):
                    for term in direction.get(key, []) or []:
                        normalised = normalize_text(str(term))
                        if len(normalised) >= 3:
                            terms.add(normalised)
                for query in direction.get("queries", []) or []:
                    terms.update(token for token in tokenize(str(query)) if len(token) >= 3)
            result[str(topic["id"])] = terms
        return result

    def _matching_topics(self, text: str) -> set[str]:
        normalised = normalize_text(text)
        tokens = tokenize(normalised)
        return {
            topic_id
            for topic_id, terms in self._terms_by_topic.items()
            if any(term in normalised or term in tokens for term in terms)
        }
