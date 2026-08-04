from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .collection import CollectionService
from .config import ConfigBundle
from .db import Database
from .demo import complete_pending_demo_tasks
from .emailer import AgentlyConfirmationRequired, EmailService, resolve_email_backend
from .expanded import rebuild_expanded_issue
from .paths import Paths, discover_root
from .pipeline import Pipeline
from .rendering import Renderer
from .review import ReviewServer, approve_issue
from .tasks import TaskService
from .utils import load_root_env, read_json, setup_logging
from .vendor import VendorManager


def _run_id(config: ConfigBundle, now: datetime | None = None) -> str:
    timezone_name = str(config.settings.get("timezone", "Asia/Shanghai"))
    try:
        configured_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(f"Invalid timezone in config/settings.yaml: {timezone_name}") from exc
    current = now.astimezone(configured_timezone) if now is not None else datetime.now(configured_timezone)
    return current.strftime("%Y-%m-%d-%H%M%S")


def _context(args):
    root = Path(args.root).resolve() if getattr(args, "root", None) else discover_root()
    paths = Paths(root)
    paths.ensure()
    config = ConfigBundle.load(paths)
    db = Database(paths.db)
    db.init()
    return root, paths, config, db


def _resolve_run(db: Database, requested: str | None) -> str:
    if requested and requested != "latest":
        if not db.fetchone("SELECT 1 FROM runs WHERE id=?", (requested,)):
            raise SystemExit(f"Run not found: {requested}")
        return requested
    latest = db.latest_run()
    if not latest:
        raise SystemExit("No run exists. Start with collect or run.")
    return latest["id"]


def cmd_setup(args) -> int:
    root, paths, config, db = _context(args)
    print(f"Workspace ready: {paths.workspace}")
    if args.vendor:
        records = VendorManager(root).install(update=args.update_vendor)
        print(json.dumps(records, ensure_ascii=False, indent=2))
    if args.node:
        subprocess.run(["npm", "install"], cwd=root, check=True)
        subprocess.run(["npx", "playwright", "install", "chromium"], cwd=root, check=True)
    return 0


def cmd_doctor(args) -> int:
    root, paths, config, db = _context(args)
    checks = []
    checks.append(("Python >= 3.10", sys.version_info >= (3, 10), sys.version.split()[0]))
    checks.append(("SQLite database", paths.db.exists(), str(paths.db)))
    for module in ("yaml", "httpx", "bs4", "jinja2", "jsonschema", "pypdf"):
        checks.append((f"Python module {module}", importlib.util.find_spec(module) is not None, ""))
    checks.append(("Node.js", shutil.which("node") is not None, shutil.which("node") or ""))
    checks.append(("Playwright package", (root / "node_modules" / "playwright").exists(), "npm install"))
    checks.append(("Guizang social card", (root / "vendor" / "guizang-social-card-skill" / "SKILL.md").exists(), "python briefing.py setup --vendor"))
    checks.append(("Guizang material illustration", (root / "vendor" / "guizang-material-illustration" / "SKILL.md").exists(), "python briefing.py setup --vendor"))
    persona = root / config.settings.get("visuals", {}).get("persona_reference", "assets/persona/reference.jpg")
    checks.append(("Persona reference (optional)", persona.exists(), str(persona)))
    backend = resolve_email_backend()
    if backend == "agently":
        executable = os.getenv("AGENTLY_CLI", "agently-cli").strip() or "agently-cli"
        checks.append(("agently-cli (required for send)", shutil.which(executable) is not None, executable))
        checks.append(("Agently recipients (required for send)", bool(os.getenv("AGENTLY_TO", "").strip() or os.getenv("EMAIL_TO", "").strip() or os.getenv("SMTP_TO", "").strip()), "AGENTLY_TO or EMAIL_TO"))
    else:
        smtp_ready = bool(
            os.getenv("SMTP_HOST", "").strip()
            and (os.getenv("EMAIL_TO", "").strip() or os.getenv("SMTP_TO", "").strip())
        )
        checks.append(("SMTP (required for send)", smtp_ready, "configure .env when ready"))
    failed_required = False
    for label, ok, detail in checks:
        symbol = "✓" if ok else "!"
        print(f"{symbol} {label}: {detail}")
        if not ok and label.startswith(("Python >=", "SQLite", "Python module")):
            failed_required = True
    return 1 if failed_required else 0


def cmd_collect(args) -> int:
    root, paths, config, db = _context(args)
    run_id = args.run or _run_id(config)
    if not db.fetchone("SELECT 1 FROM runs WHERE id=?", (run_id,)):
        db.create_run(run_id, "COLLECTING")
    run_dir = paths.runs / run_id
    service = CollectionService(config, db, run_dir)
    try:
        items = service.collect(run_id, offline_fixture=args.offline_fixture)
    finally:
        service.close()
    db.update_run(run_id, stage="COLLECTED", note=f"Collected {len(items)} items")
    print(run_id)
    print(f"Collected: {len(items)}")
    return 0



def cmd_prepare_search(args) -> int:
    root, paths, config, db = _context(args)
    run_id = _resolve_run(db, args.run)
    count = Pipeline(root, config, db, run_id).prepare_agent_search(max_queries=args.max_queries)
    print(f"Prepared Agent web-search tasks: {count}")
    task = TaskService(db, root, paths.runs / run_id).next(run_id)
    if task:
        print(TaskService(db, root, paths.runs / run_id).instructions(task))
    return 0

def cmd_prepare(args) -> int:
    root, paths, config, db = _context(args)
    run_id = _resolve_run(db, args.run)
    count = Pipeline(root, config, db, run_id).prepare_relevance()
    print(f"Prepared relevance tasks: {count}")
    task = TaskService(db, root, paths.runs / run_id).next(run_id)
    if task:
        print(TaskService(db, root, paths.runs / run_id).instructions(task))
    return 0


def cmd_tasks(args) -> int:
    root, paths, config, db = _context(args)
    run_id = _resolve_run(db, args.run)
    service = TaskService(db, root, paths.runs / run_id)
    if args.action == "next":
        task = service.next(run_id)
        print(service.instructions(task) if task else "No pending tasks")
    elif args.action == "sync":
        print(service.sync(run_id))
    elif args.action == "reopen-invalid":
        print(f"Reopened: {service.reopen_invalid(run_id)}")
    else:
        for task in service.list(run_id, args.status):
            print(f"{task['status']:9} {task['task_type']:20} {task['id']} -> {task['output_path']}")
    return 0


def cmd_advance(args) -> int:
    root, paths, config, db = _context(args)
    run_id = _resolve_run(db, args.run)
    result = Pipeline(root, config, db, run_id).advance()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["invalid"] else 0


def cmd_run(args) -> int:
    if not args.run:
        root, paths, config, db = _context(args)
        args.run = _run_id(config)
    args.offline_fixture = args.offline_fixture
    cmd_collect(args)
    root, paths, config, db = _context(args)
    run_id = _resolve_run(db, args.run)
    if args.offline_fixture:
        Pipeline(root, config, db, run_id).prepare_relevance()
    else:
        count = Pipeline(root, config, db, run_id).prepare_agent_search(
            max_queries=int(config.settings.get("agent_web_search_max_queries", 18))
        )
        if not count:
            Pipeline(root, config, db, run_id).prepare_relevance()
    return cmd_advance(args)


def cmd_resume(args) -> int:
    return cmd_advance(args)


def cmd_demo(args) -> int:
    root, paths, config, db = _context(args)
    run_id = args.run or f"demo-{_run_id(config)}"
    if not db.fetchone("SELECT 1 FROM runs WHERE id=?", (run_id,)):
        db.create_run(run_id, "COLLECTING")
    run_dir = paths.runs / run_id
    collection = CollectionService(config, db, run_dir)
    try:
        collection.collect(run_id, offline_fixture=True)
    finally:
        collection.close()
    db.update_run(run_id, stage="COLLECTED")
    pipeline = Pipeline(root, config, db, run_id)
    pipeline.prepare_relevance()
    for _ in range(10):
        completed = complete_pending_demo_tasks(root, db, run_id)
        result = pipeline.advance()
        if result["stage"] == "READY_FOR_RENDER" or not completed and not result["pending"]:
            break
    renderer = Renderer(root, config, db)
    renderer.render_issue(run_id, execute_playwright=args.render)
    EmailService(root, config, db).build(run_id)
    report = renderer.validate(run_id)
    print(json.dumps({"run_id": run_id, "stage": db.fetchone('SELECT stage FROM runs WHERE id=?', (run_id,))["stage"], "validation": report}, ensure_ascii=False, indent=2))
    return 0


def cmd_render(args) -> int:
    root, paths, config, db = _context(args)
    run_id = _resolve_run(db, args.run)
    result = Renderer(root, config, db).render_issue(run_id, execute_playwright=args.execute)
    email_path = EmailService(root, config, db).build(run_id)
    print(json.dumps({**result, "email": str(email_path)}, ensure_ascii=False, indent=2))
    return 0


def cmd_rebuild_existing(args) -> int:
    root, paths, config, db = _context(args)
    if not args.run or args.run == "latest":
        raise RuntimeError("rebuild-existing requires an explicit --run ID")
    run_id = _resolve_run(db, args.run)
    result = rebuild_expanded_issue(root, config, db, run_id, confirm=args.confirm_rebuild)
    if args.confirm_rebuild:
        result["email"] = str(EmailService(root, config, db).build(run_id))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args) -> int:
    root, paths, config, db = _context(args)
    run_id = _resolve_run(db, args.run)
    report = Renderer(root, config, db).validate(run_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report.get("failures") else 0


def cmd_review(args) -> int:
    root, paths, config, db = _context(args)
    run_id = _resolve_run(db, args.run)
    server = ReviewServer(root, db, run_id)
    if args.serve:
        server.serve(args.port)
    else:
        print(server.build_html())
    return 0



def cmd_approve(args) -> int:
    root, paths, config, db = _context(args)
    run_id = _resolve_run(db, args.run)
    if args.all:
        ids = {row["id"] for row in db.fetchall("SELECT id FROM brief_items WHERE run_id=? AND fact_check_status='PASS'", (run_id,))}
    else:
        ids = {value.strip() for value in (args.ids or "").split(",") if value.strip()}
    path = approve_issue(root, db, run_id, ids)
    print(f"Approved {len(ids)} items; rebuilt email: {path}")
    return 0

def cmd_send(args) -> int:
    root, paths, config, db = _context(args)
    run_id = _resolve_run(db, args.run)
    sent_at = EmailService(root, config, db).send(run_id, confirm=args.confirm_send)
    print(f"Sent at {sent_at}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Technical Briefing Skill CLI")
    parser.add_argument("--root", help="Skill repository root")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("setup"); p.add_argument("--vendor", action="store_true"); p.add_argument("--update-vendor", action="store_true"); p.add_argument("--node", action="store_true"); p.set_defaults(func=cmd_setup)
    p = sub.add_parser("doctor"); p.set_defaults(func=cmd_doctor)
    p = sub.add_parser("collect"); p.add_argument("--run"); p.add_argument("--offline-fixture", action="store_true"); p.set_defaults(func=cmd_collect)
    p = sub.add_parser("prepare-search"); p.add_argument("--run", default="latest"); p.add_argument("--max-queries", type=int, default=18); p.set_defaults(func=cmd_prepare_search)
    p = sub.add_parser("prepare"); p.add_argument("--run", default="latest"); p.set_defaults(func=cmd_prepare)
    p = sub.add_parser("tasks"); p.add_argument("action", choices=["list", "next", "sync", "reopen-invalid"], nargs="?", default="list"); p.add_argument("--run", default="latest"); p.add_argument("--status"); p.set_defaults(func=cmd_tasks)
    p = sub.add_parser("advance"); p.add_argument("--run", default="latest"); p.set_defaults(func=cmd_advance)
    p = sub.add_parser("run"); p.add_argument("--run"); p.add_argument("--offline-fixture", action="store_true"); p.set_defaults(func=cmd_run)
    p = sub.add_parser("resume"); p.add_argument("--run", default="latest"); p.set_defaults(func=cmd_resume)
    p = sub.add_parser("demo"); p.add_argument("--run"); p.add_argument("--render", action="store_true"); p.set_defaults(func=cmd_demo)
    p = sub.add_parser("render"); p.add_argument("--run", default="latest"); p.add_argument("--execute", action="store_true"); p.set_defaults(func=cmd_render)
    p = sub.add_parser("rebuild-existing"); p.add_argument("--run", required=True); p.add_argument("--confirm-rebuild", action="store_true"); p.set_defaults(func=cmd_rebuild_existing)
    p = sub.add_parser("validate"); p.add_argument("--run", default="latest"); p.set_defaults(func=cmd_validate)
    p = sub.add_parser("review"); p.add_argument("--run", default="latest"); p.add_argument("--serve", action="store_true"); p.add_argument("--port", type=int, default=8765); p.set_defaults(func=cmd_review)
    p = sub.add_parser("approve"); p.add_argument("--run", default="latest"); p.add_argument("--all", action="store_true"); p.add_argument("--ids"); p.set_defaults(func=cmd_approve)
    p = sub.add_parser("send"); p.add_argument("--run", default="latest"); p.add_argument("--confirm-send", action="store_true"); p.set_defaults(func=cmd_send)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else discover_root()
    try:
        load_root_env(root)
        setup_logging(root / "workspace" / "logs" / "briefing.log", args.verbose)
        return int(args.func(args))
    except KeyboardInterrupt:
        return 130
    except AgentlyConfirmationRequired as exc:
        print(f"CONFIRMATION_REQUIRED: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        if args.verbose:
            raise
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
