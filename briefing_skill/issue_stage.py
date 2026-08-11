from __future__ import annotations

from datetime import datetime, timezone

from .expanded import normalise_legacy_item, select_expanded_rows
from .tasks import synthesis_item_payload
from .utils import now_iso, read_json, stable_hash, write_json


LEGACY_VISUAL_TASKS = ("visual_routing", "illustration_brief")


def _has_legacy_visual_work(pipeline) -> bool:
    return bool(
        pipeline.db.fetchone(
            """
            SELECT 1 FROM tasks
            WHERE run_id=? AND task_type IN ('visual_routing','illustration_brief')
            LIMIT 1
            """,
            (pipeline.run_id,),
        )
    )


def _selected_issue_rows(pipeline) -> list[dict]:
    rows = pipeline.db.fetchall(
        """
        SELECT bi.*, e.topic_id, e.direction_id, e.canonical_title,
               COALESCE(
                 e.last_pushed_at,
                 (SELECT MAX(e2.last_pushed_at) FROM events e2
                  WHERE e.event_key IS NOT NULL AND e2.event_key=e.event_key)
               ) AS last_pushed_at,
               (SELECT MAX(r.published_at)
                FROM event_members em
                JOIN candidates c ON c.id=em.candidate_id
                JOIN raw_items r ON r.id=c.raw_item_id
                WHERE em.event_id=e.id) AS source_published_at
        FROM brief_items bi JOIN events e ON e.id=bi.event_id
        WHERE bi.run_id=? AND bi.fact_check_status='PASS'
        ORDER BY bi.score DESC, bi.id
        """,
        (pipeline.run_id,),
    )
    mode = pipeline.config.settings.get("issue_mode", "compact")
    if mode == "expanded_v2":
        selected, _, _, _ = select_expanded_rows(
            pipeline.root,
            pipeline.config,
            rows,
            reference_date=datetime.now(timezone.utc).date().isoformat(),
        )
        return selected

    thresholds = pipeline.config.scoring.get("thresholds", {})
    threshold = float(thresholds.get("issue_minimum", 70))
    max_items = int(thresholds.get("max_issue_items", 6))
    max_per_topic = int(thresholds.get("max_items_per_topic", 2))
    selected: list[dict] = []
    topic_counts: dict[str, int] = {}
    for row in rows:
        if float(row["score"]) < threshold:
            continue
        if row.get("last_pushed_at"):
            item = read_json(pipeline.root / row["json_path"])
            if not item.get("incremental_update"):
                continue
        topic_id = str(row["topic_id"])
        if topic_counts.get(topic_id, 0) >= max_per_topic:
            continue
        selected.append({**row, "item_role": "core"})
        topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1
        if len(selected) >= max_items:
            break
    return selected


def install_issue_stage() -> None:
    """Own issue selection/synthesis/finalization without any per-item visual work."""

    from .pipeline import Pipeline

    if getattr(Pipeline, "_explicit_issue_stage_installed", False):
        return

    legacy_prepare_issue = Pipeline._maybe_prepare_issue
    legacy_finalize_issue = Pipeline._maybe_finalize_issue

    def maybe_prepare_issue(self) -> None:
        # Archived runs that already entered the old visual workflow keep their exact
        # resume contract. New runs never create these task types.
        if _has_legacy_visual_work(self):
            return legacy_prepare_issue(self)

        pending = self.db.fetchone(
            """
            SELECT COUNT(*) AS n FROM tasks
            WHERE run_id=? AND task_type IN ('fact_check','fact_check_batch')
              AND status IN ('PENDING','INVALID','COMPLETED')
            """,
            (self.run_id,),
        )["n"]
        if pending:
            return
        if self.db.fetchone("SELECT 1 FROM issues WHERE run_id=?", (self.run_id,)):
            return

        selected = _selected_issue_rows(self)
        mode = self.config.settings.get("issue_mode", "compact")
        if not selected or (
            mode == "expanded_v2"
            and not any(row.get("item_role") == "core" for row in selected)
        ):
            return

        issue_id = stable_hash("issue", self.run_id)
        now = datetime.now(timezone.utc)
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO issues(id,run_id,status,date_from,date_to,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    issue_id,
                    self.run_id,
                    "DRAFT",
                    now.date().isoformat(),
                    now.date().isoformat(),
                    now_iso(),
                    now_iso(),
                ),
            )
            for position, row in enumerate(selected, 1):
                conn.execute(
                    """
                    INSERT INTO issue_items(issue_id,brief_item_id,position,item_role)
                    VALUES (?,?,?,?)
                    """,
                    (issue_id, row["id"], position, row.get("item_role", "core")),
                )

        self.db.update_run(
            self.run_id,
            stage="AWAITING_ISSUE_SYNTHESIS",
            issue_id=issue_id,
        )
        items = [read_json(self.root / row["json_path"]) for row in selected]
        synthesis_items = [
            synthesis_item_payload(row, item)
            for row, item in zip(selected, items)
            if row.get("item_role", "core") == "core"
        ]
        self.tasks.create(
            self.run_id,
            "issue_synthesis",
            issue_id,
            {
                "issue_id": issue_id,
                "items": synthesis_items,
                "max_judgements": 3,
                "audience": "公司内部领导和技术同事",
            },
            prompt="issue-synthesis.md",
            schema="issue-synthesis.schema.json",
            priority=100,
        )

    def maybe_finalize_issue(self) -> None:
        if _has_legacy_visual_work(self):
            return legacy_finalize_issue(self)

        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (self.run_id,))
        if not issue or not issue.get("synthesis_path"):
            return
        unfinished = self.db.fetchone(
            """
            SELECT COUNT(*) AS n FROM tasks
            WHERE run_id=? AND task_type='issue_synthesis'
              AND status IN ('PENDING','INVALID','COMPLETED')
            """,
            (self.run_id,),
        )["n"]
        if unfinished:
            return

        item_rows = self.db.fetchall(
            """
            SELECT ii.position,ii.item_role,bi.*,e.topic_id,e.direction_id
            FROM issue_items ii
            JOIN brief_items bi ON bi.id=ii.brief_item_id
            JOIN events e ON e.id=bi.event_id
            WHERE ii.issue_id=? ORDER BY ii.position
            """,
            (issue["id"],),
        )
        issue_data = {
            "id": issue["id"],
            "run_id": self.run_id,
            "date_from": issue["date_from"],
            "date_to": issue["date_to"],
            "synthesis": read_json(self.root / issue["synthesis_path"]),
            "layout_mode": self.config.settings.get("issue_mode", "compact"),
            "core_items": [],
            "observations": [],
            "items": [],
        }
        for row in item_rows:
            item = read_json(self.root / row["json_path"])
            if self.config.settings.get("issue_mode", "compact") == "expanded_v2":
                item = normalise_legacy_item(item, self.config)
            item_role = row.get("item_role") or "core"
            rebuilt = {
                **item,
                "brief_item_id": row["id"],
                "topic_id": row["topic_id"],
                "direction_id": row["direction_id"],
                "item_role": item_role,
                "fact_check_status": row.get("fact_check_status"),
                "anchor_id": f"item-{row['id']}",
            }
            issue_data["items"].append(rebuilt)
            issue_data["core_items" if item_role == "core" else "observations"].append(rebuilt)

        path = self.run_dir / "issue" / "issue.json"
        write_json(path, issue_data)
        self.db.execute(
            """
            UPDATE issues SET issue_json_path=?,status='READY_FOR_RENDER',updated_at=?
            WHERE id=?
            """,
            (str(path.relative_to(self.root)), now_iso(), issue["id"]),
        )
        self.db.update_run(self.run_id, stage="READY_FOR_RENDER")

    Pipeline._maybe_prepare_issue = maybe_prepare_issue
    Pipeline._maybe_finalize_issue = maybe_finalize_issue
    Pipeline._explicit_issue_stage_installed = True
