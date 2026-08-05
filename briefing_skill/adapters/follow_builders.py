from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any

from ..config import ConfigBundle
from ..db import Database
from ..http import HttpClient
from ..utils import complete_sentence_excerpt, normalize_text, stable_hash
from .base import CollectedItem

LOGGER = logging.getLogger(__name__)


class FollowBuildersCollector:
    """Collect builder signals without treating them as primary evidence."""

    def __init__(self, config: ConfigBundle, db: Database, http: HttpClient, run_dir: Path):
        self.config = config
        self.db = db
        self.http = http
        self.run_dir = run_dir
        self.source = next(
            (source for source in config.source_list() if source.get("type") == "follow_builders"),
            None,
        )

    def collect(self) -> list[CollectedItem]:
        if not self.source or not self.source.get("enabled", True):
            return []
        items: list[CollectedItem] = []
        for feed_kind, url in (self.source.get("feeds") or {}).items():
            try:
                payload = self._fetch_feed(str(feed_kind), str(url))
                if payload is None:
                    continue
                if feed_kind == "x":
                    items.extend(self._x_items(payload))
                elif feed_kind == "podcasts":
                    items.extend(self._podcast_items(payload))
                elif feed_kind == "blogs":
                    items.extend(self._blog_items(payload))
            except Exception as exc:
                LOGGER.warning("Follow Builders feed failed %s: %s", feed_kind, exc)
        return items

    def _fetch_feed(self, feed_kind: str, url: str) -> dict[str, Any] | None:
        state_key = f"follow-builders:{feed_kind}:{url}"
        state = self.db.get_source_state(state_key) or {}
        headers = {"If-None-Match": state["etag"]} if state.get("etag") else None
        response = self.http.get(url, headers=headers)
        if response.status_code == 304:
            return None
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Follow Builders {feed_kind} feed is not a JSON object")
        self.db.upsert_source_state(
            state_key,
            etag=response.headers.get("ETag"),
            payload={"feed_kind": feed_kind, "url": url},
        )
        return payload

    def _base_priority(self, feed_kind: str) -> float:
        return float((self.source.get("base_priorities") or {}).get(feed_kind, 0))

    @staticmethod
    def _tweet_title(text: str) -> str:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), text.strip())
        return complete_sentence_excerpt(first_line, 120)

    def _x_items(self, payload: dict[str, Any]) -> list[CollectedItem]:
        generated_at = payload.get("generatedAt") or payload.get("generated_at")
        limit = int(self.source.get("max_x_items", 40))
        min_chars = int(self.source.get("skip_short_x_chars", 60))
        result: list[CollectedItem] = []
        for builder in payload.get("x") or []:
            name = str(builder.get("name") or builder.get("handle") or "Unknown builder").strip()
            handle = str(builder.get("handle") or "").strip()
            bio = str(builder.get("bio") or "").strip()
            for tweet in builder.get("tweets") or []:
                text = re.sub(r"\s+", " ", str(tweet.get("text") or "")).strip()
                if self._low_information_tweet(text, min_chars):
                    continue
                engagement = sum(self._number(tweet.get(key)) for key in ("likes", "retweets", "replies"))
                topic_hint, boost = self._topic_signal(text)
                priority = (self._base_priority("x") + min(4.0, math.log10(engagement + 1.0))) * boost
                result.append(
                    CollectedItem(
                        source_id="follow_builders_x",
                        discovery_source=f"Follow Builders / X / {name}",
                        source_level="B",
                        discovery_only=True,
                        title=self._tweet_title(text),
                        summary=text,
                        original_url=str(tweet.get("url") or ""),
                        published_at=tweet.get("createdAt") or tweet.get("created_at"),
                        discovered_at=generated_at,
                        authors=[name],
                        external_id=str(tweet.get("id") or ""),
                        topic_hint=topic_hint,
                        priority=priority,
                        payload={
                            "handle": handle,
                            "bio": bio,
                            "likes": self._number(tweet.get("likes")),
                            "retweets": self._number(tweet.get("retweets")),
                            "replies": self._number(tweet.get("replies")),
                            "feed_generated_at": generated_at,
                            "source_role": "people_signal",
                        },
                    )
                )
                if len(result) >= limit:
                    return result
        return result

    @staticmethod
    def _number(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _low_information_tweet(text: str, min_chars: int) -> bool:
        if not text:
            return True
        without_urls = re.sub(r"https?://\S+", "", text).strip(" .,!?:;，。！？：；")
        if not without_urls:
            return True
        compact = re.sub(r"\s+", " ", without_urls).strip().lower()
        confirmations = {
            "yes",
            "yep",
            "nice",
            "great",
            "agreed",
            "confirmation here",
            "nice use case",
        }
        if len(compact) >= min_chars:
            return False
        return compact in confirmations or bool(
            re.fullmatch(r"(?:yes|yep|nice|great|agreed|true|exactly|confirmed)(?:[.! ]+)?", compact)
        )

    def _podcast_items(self, payload: dict[str, Any]) -> list[CollectedItem]:
        generated_at = payload.get("generatedAt") or payload.get("generated_at")
        result: list[CollectedItem] = []
        for episode in (payload.get("podcasts") or [])[: int(self.source.get("max_podcast_items", 8))]:
            title = str(episode.get("title") or "Untitled podcast episode").strip()
            podcast_name = str(episode.get("name") or "Podcast").strip()
            guid = str(episode.get("guid") or stable_hash(podcast_name, title, episode.get("url")))
            transcript = str(episode.get("transcript") or "").strip()
            topic_hint, boost = self._topic_signal(f"{title} {transcript[:2000]}")
            relative_path = ""
            if transcript:
                safe_guid = re.sub(r"[^0-9A-Za-z._-]+", "-", guid).strip("-.") or stable_hash(guid)
                transcript_path = (
                    self.run_dir
                    / "source-cache"
                    / "follow-builders"
                    / "podcasts"
                    / f"{safe_guid}.md"
                )
                transcript_path.parent.mkdir(parents=True, exist_ok=True)
                transcript_path.write_text(
                    "\n\n".join(
                        [
                            f"# {title}",
                            f"播客名称：{podcast_name}",
                            f"原始URL：{episode.get('url') or ''}",
                            f"发布时间：{episode.get('publishedAt') or episode.get('published_at') or ''}",
                            "## Transcript",
                            transcript,
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                relative_path = str(transcript_path.relative_to(self.run_dir))
            result.append(
                CollectedItem(
                    source_id="follow_builders_podcast",
                    discovery_source=f"Follow Builders / Podcast / {podcast_name}",
                    source_level="B",
                    discovery_only=True,
                    title=title,
                    summary=f"{podcast_name} 近期访谈条目；完整 transcript 已保存为本地全文。",
                    original_url=str(episode.get("url") or ""),
                    published_at=episode.get("publishedAt") or episode.get("published_at"),
                    discovered_at=generated_at,
                    authors=[podcast_name],
                    external_id=guid,
                    topic_hint=topic_hint,
                    priority=self._base_priority("podcasts") * boost,
                    payload={
                        "podcast_name": podcast_name,
                        "local_fulltext_path": relative_path,
                        "feed_generated_at": generated_at,
                        "source_role": "builder_interview",
                    },
                )
            )
        return result

    def _blog_items(self, payload: dict[str, Any]) -> list[CollectedItem]:
        generated_at = payload.get("generatedAt") or payload.get("generated_at")
        candidates = payload.get("blogs") or payload.get("items") or []
        result: list[CollectedItem] = []
        for blog in candidates[: int(self.source.get("max_blog_items", 20))]:
            url = str(blog.get("url") or blog.get("link") or "").strip()
            title = str(blog.get("title") or "Untitled blog post").strip()
            if not url:
                continue
            content = str(blog.get("content") or "").strip()
            relative_path = ""
            if len(content) >= 500:
                identity = str(blog.get("id") or blog.get("guid") or stable_hash(url))
                safe_id = re.sub(r"[^0-9A-Za-z._-]+", "-", identity).strip("-.") or stable_hash(identity)
                content_path = self.run_dir / "source-cache" / "follow-builders" / "blogs" / f"{safe_id}.md"
                content_path.parent.mkdir(parents=True, exist_ok=True)
                content_path.write_text(
                    f"# {title}\n\n原始URL：{url}\n\n## Content\n\n{content}\n",
                    encoding="utf-8",
                )
                relative_path = str(content_path.relative_to(self.run_dir))
            summary = str(blog.get("summary") or blog.get("description") or "").strip()
            if not summary and content:
                summary = complete_sentence_excerpt(content, 280)
            topic_hint, boost = self._topic_signal(f"{title} {summary} {content[:2000]}")
            metadata = {
                key: value
                for key, value in blog.items()
                if key not in {"content", "summary", "description"}
            }
            metadata.update(
                {
                    "local_fulltext_path": relative_path,
                    "feed_generated_at": generated_at,
                    "source_role": "builder_blog",
                }
            )
            author = str(blog.get("author") or blog.get("name") or "").strip()
            result.append(
                CollectedItem(
                    source_id="follow_builders_blog",
                    discovery_source="Follow Builders / Blog",
                    source_level="B",
                    discovery_only=True,
                    title=title,
                    summary=summary,
                    original_url=url,
                    published_at=blog.get("publishedAt") or blog.get("published_at"),
                    discovered_at=generated_at,
                    authors=[author] if author else [],
                    external_id=str(blog.get("id") or blog.get("guid") or stable_hash(url)),
                    topic_hint=topic_hint,
                    priority=self._base_priority("blogs") * boost,
                    payload=metadata,
                )
            )
        return result

    def _topic_signal(self, text: str) -> tuple[str, float]:
        normalised = normalize_text(text)
        ranked: list[tuple[int, float, str]] = []
        boosts = self.source.get("topic_boosts") or {}
        for topic in self.config.topic_list():
            terms: set[str] = set()
            for direction in topic.get("directions", []):
                for key in ("include_terms", "aihot_boost_terms"):
                    terms.update(
                        normalize_text(str(term))
                        for term in direction.get(key, []) or []
                        if len(normalize_text(str(term))) >= 3
                    )
            hits = sum(1 for term in terms if term and term in normalised)
            if hits:
                ranked.append((hits, float(boosts.get(topic["id"], 1.0)), str(topic["id"])))
        if not ranked:
            return "", 1.0
        _, boost, topic_id = max(ranked, key=lambda value: (value[0], value[1], value[2]))
        return topic_id, boost
