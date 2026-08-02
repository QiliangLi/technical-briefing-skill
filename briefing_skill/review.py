from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import ConfigBundle
from .db import Database
from .emailer import EmailService
from .paths import Paths
from .utils import read_json, write_json


def approve_issue(root: Path, db: Database, run_id: str, approved_ids: set[str]) -> Path:
    issue = db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
    if not issue or not issue.get("issue_json_path"):
        raise RuntimeError("Issue not ready")

    selectable = {
        row["id"]
        for row in db.fetchall(
            "SELECT bi.id FROM issue_items ii JOIN brief_items bi ON bi.id=ii.brief_item_id "
            "WHERE ii.issue_id=? AND bi.fact_check_status='PASS'",
            (issue["id"],),
        )
    }
    approved_ids = approved_ids & selectable
    if not approved_ids:
        raise ValueError("At least one fact-checked issue item must be approved")

    for item_id in selectable:
        db.execute("UPDATE brief_items SET approved=? WHERE id=?", (int(item_id in approved_ids), item_id))

    # Rebuild from immutable item JSON files instead of destructively filtering the
    # previous issue JSON. This allows a reviewer to reopen the page and change the
    # selection without losing rejected candidates.
    rows = db.fetchall(
        """
        SELECT ii.position, ii.visual_plan_path, bi.id, bi.json_path,
               e.topic_id, e.direction_id
        FROM issue_items ii
        JOIN brief_items bi ON bi.id=ii.brief_item_id
        JOIN events e ON e.id=bi.event_id
        WHERE ii.issue_id=? ORDER BY ii.position
        """,
        (issue["id"],),
    )
    issue_path = root / issue["issue_json_path"]
    previous = read_json(issue_path)
    previous_items = {
        item.get("brief_item_id"): item
        for item in previous.get("items", [])
        if item.get("brief_item_id")
    }
    rebuilt = {
        "id": issue["id"],
        "run_id": run_id,
        "date_from": issue.get("date_from"),
        "date_to": issue.get("date_to"),
        "synthesis": previous.get("synthesis") or read_json(root / issue.get("synthesis_path", ""), {}),
        "items": [],
    }
    run_dir = root / "workspace" / "runs" / run_id
    for row in rows:
        if row["id"] not in approved_ids:
            continue
        item = read_json(root / row["json_path"])
        previous_item = previous_items.get(row["id"], {})
        plan = previous_item.get("visual_plan")
        if not isinstance(plan, dict):
            plan = read_json(root / row["visual_plan_path"], {}) if row.get("visual_plan_path") else {"visual_mode": "text_only"}
        illustration = read_json(run_dir / "visuals" / "illustrations" / f"{row['id']}.json", {})
        rebuilt["items"].append(
            {
                **item,
                "brief_item_id": row["id"],
                "topic_id": row["topic_id"],
                "direction_id": row["direction_id"],
                "visual_plan": plan,
                "illustration": illustration,
            }
        )
    write_json(issue_path, rebuilt)
    db.execute("UPDATE issues SET status='APPROVED' WHERE id=?", (issue["id"],))
    return EmailService(root, ConfigBundle.load(Paths(root)), db).build(run_id, status_after="APPROVED")


class ReviewServer:
    def __init__(self, root: Path, db: Database, run_id: str):
        self.root = root
        self.db = db
        self.run_id = run_id

    def build_html(self) -> Path:
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (self.run_id,))
        if not issue or not issue.get("issue_json_path"):
            raise RuntimeError("Issue not ready")
        data = read_json(self.root / issue["issue_json_path"])
        env = Environment(loader=FileSystemLoader(self.root / "templates"), autoescape=select_autoescape(["html"]))
        html_text = env.get_template("review.html").render(issue=data, run_id=self.run_id)
        path = self.root / "workspace" / "runs" / self.run_id / "review.html"
        path.write_text(html_text, encoding="utf-8")
        return path

    def serve(self, port: int = 8765) -> None:
        html_path = self.build_html()
        root = self.root
        db = self.db
        run_id = self.run_id

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in {"/", "/review.html"}:
                    content = html_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
                self.send_error(404)

            def do_POST(self):
                if self.path != "/approve":
                    self.send_error(404)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                approved_ids = set(payload.get("approved_ids", []))
                try:
                    approve_issue(root, db, run_id, approved_ids)
                    content = b'{"ok":true}'
                    status = 200
                except Exception as exc:
                    content = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False).encode("utf-8")
                    status = 400
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        print(f"Review page: http://127.0.0.1:{port}")
        server.serve_forever()
