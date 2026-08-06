from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .db import Database
from .utils import normalize_text, stable_hash, title_similarity


@dataclass
class Cluster:
    topic_id: str
    direction_id: str
    members: list[dict[str, Any]]


class EventClusterer:
    def __init__(self, db: Database):
        self.db = db

    def cluster_run(self, run_id: str) -> list[Cluster]:
        rows = self.db.fetchall(
            """
            SELECT f.candidate_id, f.json_path, f.quality_score, f.event_hint,
                   c.topic_id, c.direction_id, c.relevance_score, c.rule_score,
                   r.title, r.canonical_url,
                   r.identity_key, r.published_at
            FROM facts f
            JOIN candidates c ON c.id=f.candidate_id
            JOIN raw_items r ON r.id=c.raw_item_id
            WHERE f.run_id=?
            ORDER BY f.quality_score DESC,
                     COALESCE(c.relevance_score, 0) DESC,
                     c.rule_score DESC,
                     c.id
            """,
            (run_id,),
        )
        groups: list[Cluster] = []
        for row in rows:
            placed = False
            for cluster in groups:
                if self._same_event(row, cluster.members[0]):
                    cluster.members.append(row)
                    placed = True
                    break
            if not placed:
                groups.append(Cluster(row["topic_id"], row["direction_id"], [row]))
        return groups

    @staticmethod
    def _same_event(a: dict[str, Any], b: dict[str, Any]) -> bool:
        if a.get("identity_key") and a.get("identity_key") == b.get("identity_key"):
            return True
        if a.get("event_hint") and b.get("event_hint"):
            if title_similarity(a["event_hint"], b["event_hint"]) >= 0.72:
                return True
        return title_similarity(a.get("title"), b.get("title")) >= 0.72

    def persist(self, run_id: str, clusters: list[Cluster]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for cluster in clusters:
            primary = cluster.members[0]
            identities = sorted({str(member.get("identity_key")) for member in cluster.members if member.get("identity_key")})
            event_key = identities[0] if identities else (
                f"semantic:{cluster.topic_id}:{stable_hash(normalize_text(primary.get('event_hint') or primary['title']))}"
            )
            fingerprint = stable_hash("event-key", event_key)
            existing = self.db.fetchone(
                """
                SELECT * FROM events WHERE event_key=?
                ORDER BY (last_pushed_at IS NOT NULL) DESC, first_seen_at, id LIMIT 1
                """,
                (event_key,),
            )
            if not existing:
                existing = self.db.fetchone("SELECT * FROM events WHERE fingerprint=?", (fingerprint,))
            event_id = existing["id"] if existing else stable_hash("event", fingerprint)
            payload = {
                "run_id": run_id,
                "members": [member["candidate_id"] for member in cluster.members],
                "sources": [member.get("canonical_url") for member in cluster.members],
            }
            now = __import__("briefing_skill.utils", fromlist=["now_iso"]).now_iso()
            with self.db.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO events(id, topic_id, direction_id, canonical_title, fingerprint, event_key,
                                       score, first_seen_at, last_updated_at, last_pushed_at, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        topic_id=CASE
                            WHEN events.last_pushed_at IS NOT NULL THEN events.topic_id
                            ELSE excluded.topic_id
                        END,
                        direction_id=CASE
                            WHEN events.last_pushed_at IS NOT NULL THEN events.direction_id
                            ELSE excluded.direction_id
                        END,
                        last_updated_at=excluded.last_updated_at,
                        event_key=excluded.event_key,
                        payload_json=excluded.payload_json,
                        score=MAX(events.score, excluded.score)
                    """,
                    (
                        event_id,
                        cluster.topic_id,
                        cluster.direction_id,
                        primary.get("event_hint") or primary["title"],
                        fingerprint,
                        event_key,
                        max(float(member.get("quality_score") or 0) for member in cluster.members),
                        existing["first_seen_at"] if existing else now,
                        now,
                        existing.get("last_pushed_at") if existing else None,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )
                for member in cluster.members:
                    conn.execute(
                        "INSERT OR IGNORE INTO event_members(event_id, candidate_id, run_id) VALUES (?, ?, ?)",
                        (event_id, member["candidate_id"], run_id),
                    )
            persisted = self.db.fetchone("SELECT topic_id, direction_id FROM events WHERE id=?", (event_id,))
            result.append(
                {
                    "event_id": event_id,
                    "topic_id": persisted["topic_id"],
                    "direction_id": persisted["direction_id"],
                    "members": cluster.members,
                }
            )
        return result
