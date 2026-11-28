"""Commands for running and watching the group assistant.

``serve`` is the resident process and the command that talks to Feishu;
``report to`` opens the private channel to the owner once. Everything else
reads or changes local state through the same store.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

from . import e2e, tasks
from .common import context, emit, load_index
from .config import AssistantConfigError, normalize_chat_id, write_local_config
from .engine import Engine, candidate
from . import discussions, feedback
from .lark import LarkClient, LarkTransport
from .policy import MODES, Policy
from .service import AlreadyRunning, Service, overview, process_alive, request_stop
from .store import Store
from .timeutil import iso

DURATION = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")
OPEN_ID = re.compile(r"^ou_[0-9a-f]{32}$")
# What a host session gets back from one search of its own.
SEARCH_HITS = 8
DIRECT_OPENING = "群助手：以后在这里向你汇报群里讨论到、而日报没覆盖的方向，以及它自己的状态。"


def parse_duration(text: str) -> float:
    """``90s``, ``30m``, ``2h``, ``1d`` or a combination such as ``1d2h``, in seconds."""

    match = DURATION.fullmatch(text.strip())
    if not match or not any(match.groups()):
        raise ValueError(f"Not a duration: {text!r}; use 30m, 2h, 1d or off")
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def policy_view(policy: Policy, now: float) -> dict[str, Any]:
    return {
        "explicit": policy.explicit,
        "proactive": policy.proactive,
        "muted_for_seconds": max(0, round(policy.muted_until - now)) if policy.muted_until else 0,
        "version": policy.version,
    }


def _nested(rows: list[dict[str, Any]], outer: str, inner: str) -> dict[str, dict[str, int]]:
    nested: dict[str, dict[str, int]] = {}
    for row in rows:
        nested.setdefault(row[outer], {})[row[inner]] = row["n"]
    return nested


# ---- the resident process ----


def cmd_serve(args: argparse.Namespace) -> int:
    root, config, state_dir = context(args)
    if args.detach:
        return _start_detached(root, state_dir)
    service = Service(root, config, state_dir, client=LarkClient(config))
    try:
        code = service.run()
    except AlreadyRunning as exc:
        emit({"error": str(exc)})
        return 1
    if code:
        emit({"error": service.store.get_meta("service", {}).get("error") or "the resident process stopped with an error"})
    return code


def _start_detached(root: Path, state_dir: Path) -> int:
    """Start the resident process on its own, so that it outlives any session that launched it."""

    pid_path = state_dir / "service.pid"
    if pid_path.exists():
        pid = int(pid_path.read_text().strip() or 0)
        if pid and process_alive(pid):
            emit({"started": False, "running": True, "pid": pid, "log": str(state_dir / "serve.log")})
            return 0
    state_dir.mkdir(parents=True, exist_ok=True)
    log_path = state_dir / "serve.log"
    with log_path.open("a", encoding="utf-8") as log:
        child = subprocess.Popen(
            [sys.executable, str(root / "briefing.py"), "assistant", "--state-dir", str(state_dir), "serve"],
            cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
        )
    emit({"started": True, "pid": child.pid, "log": str(log_path), "stop": "python briefing.py assistant stop"})
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    _, _, state_dir = context(args)
    emit(request_stop(state_dir))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root, config, state_dir = context(args)
    report = overview(Store(state_dir / "assistant.sqlite"), root, config, state_dir, time.time())
    emit(report)
    return 0 if report["service"]["running"] and report["self_check"]["ok"] else 1


# ---- what the assistant responds to ----


def cmd_mode(args: argparse.Namespace) -> int:
    _, _, state_dir = context(args)
    store = Store(state_dir / "assistant.sqlite")
    policy = Policy.load(store)
    if args.mode_kind == "explicit":
        policy.explicit = args.value == "on"
    else:
        policy.proactive = args.value
    policy.save(store)
    emit(policy_view(policy, time.time()))
    return 0


def cmd_mute(args: argparse.Namespace) -> int:
    _, _, state_dir = context(args)
    store = Store(state_dir / "assistant.sqlite")
    policy = Policy.load(store)
    try:
        policy.muted_until = 0.0 if args.duration == "off" else time.time() + parse_duration(args.duration)
    except ValueError as exc:
        emit({"error": str(exc)})
        return 1
    policy.save(store)
    emit({**policy_view(policy, time.time()), "muted_until": iso(policy.muted_until) if policy.muted_until else None})
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    _, config, state_dir = context(args)
    if args.chat_action == "list":
        emit({"chats": list(config.chat_whitelist)})
        return 0
    chats = list(config.chat_whitelist)
    try:
        chat_id = normalize_chat_id(args.chat_id)
    except AssistantConfigError as exc:
        emit({"error": str(exc)})
        return 1
    if args.chat_action == "add" and chat_id not in chats:
        chats.append(chat_id)
    elif args.chat_action == "remove" and chat_id in chats:
        chats.remove(chat_id)
    write_local_config(state_dir, chat_whitelist=chats)
    emit(
        {
            "chats": chats,
            "note": "A running process keeps the whitelist it started with; restart it to apply the change.",
        }
    )
    return 0


# ---- the host session's side ----


def cmd_tasks(args: argparse.Namespace) -> int:
    root, config, state_dir = context(args)
    store = Store(state_dir / "assistant.sqlite")
    if args.tasks_action == "wait":
        emit(tasks.wait(store, root, timeout=args.timeout))
        return 0
    task = tasks.get(store, args.task)
    if task is None:
        emit({"error": f"Unknown task: {args.task}"})
        return 1
    if args.tasks_action == "card":
        emit(tasks.card(task, root))
        return 0
    engine = Engine(store, load_index(root, config, state_dir), config, root, state_dir)
    path = Path(args.output) if args.output else Path(task["output_path"])
    output, error = tasks.read_output({**task, "output_path": str(path)})
    result = engine.apply_task(task["task_id"], output, output_error=error)
    emit(result)
    return 0 if result["ok"] else 1


def cmd_search(args: argparse.Namespace) -> int:
    """A host session's own search: what it returns is what the session may cite."""

    root, config, state_dir = context(args)
    store = Store(state_dir / "assistant.sqlite")
    task = tasks.searchable(store, args.task)
    if task is None:
        emit({"error": f"No pending task to search for: {args.task}"})
        return 1
    hits = load_index(root, config, state_dir).search(args.query, SEARCH_HITS)
    if not tasks.log_search(store, args.task, args.query, [hit["doc"]["id"] for hit in hits], time.time()):
        emit({"error": "This task has used its searches", "hits": []})
        return 1
    emit({"task": args.task, "hits": [candidate(hit["doc"], hit["score"]) for hit in hits]})
    return 0


# ---- watching ----


def review(store: Store, index: Any, days: int, act: str | None = None) -> dict[str, Any]:
    """What the assistant decided about the group's discussions, including when it held its tongue."""

    rows = store.fetchall(
        "SELECT * FROM decisions WHERE kind='contribute' AND created_at >= ? ORDER BY created_at DESC",
        (iso(time.time() - days * 86400),),
    )
    decisions = []
    for row in rows:
        if act and row["act"] != act:
            continue
        decisions.append(
            {
                "at": row["created_at"], "mode": row["mode"], "act": row["act"], "outcome": row["outcome"],
                "thread": row["thread_key"],
                "documents": [
                    {"id": doc_id, "title": (index.get(doc_id) or {}).get("headline")} for doc_id in json.loads(row["doc_ids_json"])
                ],
                "draft": row["draft"],
            }
        )
    by_act: dict[str, dict[str, int]] = {}
    for row in rows:
        by_act.setdefault(row["act"] or "-", {})[row["outcome"]] = by_act.setdefault(row["act"] or "-", {}).get(row["outcome"], 0) + 1
    return {"days": days, "act": act, "by_act": by_act, "decisions": decisions}


def stats(store: Store, days: int) -> dict[str, Any]:
    """Counts behind a trial: what came in, what was decided, what left, what was reported."""

    since = iso(time.time() - days * 86400)
    return {
        "days": days,
        "dispositions": _nested(
            store.fetchall(
                "SELECT decision, reason, COUNT(*) AS n FROM dispositions WHERE updated_at >= ? GROUP BY decision, reason", (since,)
            ),
            "decision", "reason",
        ),
        "decisions": _nested(
            store.fetchall("SELECT kind, outcome, COUNT(*) AS n FROM decisions WHERE created_at >= ? GROUP BY kind, outcome", (since,)),
            "kind", "outcome",
        ),
        "acts": _nested(
            store.fetchall("SELECT act, outcome, COUNT(*) AS n FROM decisions WHERE kind='contribute' AND created_at >= ? GROUP BY act, outcome", (since,)),
            "act", "outcome",
        ),
        "outbox": _nested(
            store.fetchall("SELECT kind, status, COUNT(*) AS n FROM outbox GROUP BY kind, status"), "kind", "status"
        ),
        "tasks": _nested(store.fetchall("SELECT kind, status, COUNT(*) AS n FROM tasks GROUP BY kind, status"), "kind", "status"),
        "searches": store.fetchone("SELECT COUNT(*) AS n FROM task_searches")["n"],
        "feedback": _nested(store.fetchall("SELECT source, choice, COUNT(*) AS n FROM feedback GROUP BY source, choice"), "source", "choice"),
        "reports": _nested(store.fetchall("SELECT kind, status, COUNT(*) AS n FROM reports GROUP BY kind, status"), "kind", "status"),
        "pauses": [
            {"at": row["created_at"], "reason": row["reason"]}
            for row in store.fetchall("SELECT * FROM pause_log WHERE created_at >= ? ORDER BY id", (since,))
        ],
    }


def cmd_review(args: argparse.Namespace) -> int:
    root, config, state_dir = context(args)
    emit(review(Store(state_dir / "assistant.sqlite"), load_index(root, config, state_dir), args.days, args.act))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    _, _, state_dir = context(args)
    emit(stats(Store(state_dir / "assistant.sqlite"), args.days))
    return 0


# ---- reports to the owner ----


def cmd_report(args: argparse.Namespace) -> int:
    root, config, state_dir = context(args)
    store = Store(state_dir / "assistant.sqlite")
    if args.report_action == "to":
        if not OPEN_ID.match(args.open_id):
            emit({"error": "Not an open_id (ou_…)"})
            return 1
        opened = LarkClient(config).open_direct_chat(args.open_id, DIRECT_OPENING)
        chat_id = str(opened.get("chat_id") or "")
        if not chat_id:
            emit({"error": "The platform did not say which chat the message went to", "result": opened})
            return 1
        store.set_meta("report_to", {"open_id": args.open_id, "chat_id": chat_id})
        emit({"report_to": {"open_id": args.open_id, "chat_id": chat_id}})
        return 0
    if args.report_action == "show":
        row = store.fetchone("SELECT * FROM reports WHERE id=?", (args.id,))
        if row is None:
            emit({"error": f"Unknown report: {args.id}"})
            return 1
        body = json.loads(row["body_json"])
        if row["kind"] == "gap":
            emit({
                "id": row["id"], "at": row["created_at"], "status": row["status"], "names": body["names"],
                "messages": body["texts"], "summary": body["summary"], "nearest": body["nearest_label"] or None,
                "terms": body["terms"], "placement": body["placement"],
            })
        else:
            emit({"id": row["id"], "at": row["created_at"], "status": row["status"], "text": body["text"]})
        return 0
    since = iso(time.time() - args.days * 86400)
    rows = store.fetchall("SELECT * FROM reports WHERE created_at >= ? ORDER BY created_at DESC", (since,))
    emit(
        {
            "days": args.days,
            "report_to": store.get_meta("report_to"),
            "reports": [
                {
                    "id": row["id"], "kind": row["kind"], "at": row["created_at"], "status": row["status"],
                    "title": row["title"], **({"names": json.loads(row["body_json"])["names"]} if row["kind"] == "gap" else {}),
                }
                for row in rows
            ],
        }
    )
    return 0


# ---- idea cards ----


def cmd_feedback(args: argparse.Namespace) -> int:
    root, config, state_dir = context(args)
    store = Store(state_dir / "assistant.sqlite")
    now = time.time()
    try:
        issue = date.fromisoformat(args.issue).isoformat() if getattr(args, "issue", None) else None
        if args.feedback_action == "prepare":
            result: dict[str, Any] = feedback.prepare(root, config, state_dir, store, issue, now)
        elif args.feedback_action == "push":
            result = feedback.push(
                root, config, state_dir, store, issue, LarkTransport(config), confirm=args.confirm_send, now=now
            )
        elif args.feedback_action == "collect":
            result = feedback.collect(store, LarkClient(config), now)
        else:
            result = feedback.summary(store)
    except (ValueError, feedback.FeedbackError) as exc:
        emit({"error": str(exc)})
        return 1
    emit(result)
    return 1 if result.get("error") else 0


# ---- end-to-end checks ----


def cmd_e2e(args: argparse.Namespace) -> int:
    """``e2e`` replays offline; ``e2e --live`` speaks to the test group as the user."""

    root, _, _ = context(args)
    if not args.live:
        return e2e.replay(root)
    if args.only and not args.discussions:
        emit({"error": "--only narrows --discussions; add --discussions"})
        return 2
    try:
        e2e.check_chat(args.chat)
        scenarios = discussions.load(root, args.only.split(",") if args.only else None) if args.discussions else None
    except (e2e.E2EError, ValueError) as exc:
        emit({"error": str(exc)})
        return 2
    live = e2e.Live(root)
    if scenarios is not None:
        report = live.discuss(scenarios, session=args.session, session_wait=args.session_wait)
    elif args.soak_minutes:
        report = live.soak(args.soak_minutes)
    else:
        report = live.run()
    emit(report)
    return 0 if report["ok"] else 1


# ---- parser ----


def add_parsers(actions: argparse._SubParsersAction) -> None:
    def command(name: str, helper: str, func: Any) -> argparse.ArgumentParser:
        parser = actions.add_parser(name, help=helper)
        parser.set_defaults(func=func)
        return parser

    serve = command("serve", "run the resident process until it is stopped", cmd_serve)
    serve.add_argument("--detach", action="store_true", help="start it on its own and return at once")
    command("stop", "stop the resident process", cmd_stop)
    command("status", "heartbeat, consumers, index, today's counts and the self-check", cmd_status)

    e2e_command = command("e2e", "replay the offline suites; with --live, run against the test group as the user", cmd_e2e)
    e2e_command.add_argument("--live", action="store_true", help="send real messages to the test group as the user")
    e2e_command.add_argument("--chat", help="the group for a live run; only the test group is accepted")
    e2e_command.add_argument("--soak-minutes", type=int, default=0, help="with --live: keep the process up and probe it instead of running the scenarios")
    e2e_command.add_argument("--discussions", action="store_true", help="with --live: hold simulated discussions and judge the replies")
    e2e_command.add_argument("--only", help="comma-separated scenario ids for --discussions")
    e2e_command.add_argument("--session", choices=["stand-in", "manual"], default="stand-in", help="with --discussions: who executes the tasks")
    e2e_command.add_argument("--session-wait", type=float, default=e2e.DISCUSSION_TIMEOUT, help="with --discussions: seconds to wait for each reply")

    mode = command("mode", "change what the assistant responds to", cmd_mode)
    mode_kind = mode.add_subparsers(dest="mode_kind", required=True)
    explicit = mode_kind.add_parser("explicit", help="answer the messages that address it")
    explicit.add_argument("value", choices=["on", "off"])
    explicit.set_defaults(func=cmd_mode)
    proactive = mode_kind.add_parser("proactive", help="take part in unaddressed discussions: off, observe (decide and record only) or auto (speak)")
    proactive.add_argument("value", choices=list(MODES))
    proactive.set_defaults(func=cmd_mode)

    mute = command("mute", "pause proactive replies for a while, or lift the pause with `off`", cmd_mute)
    mute.add_argument("duration", nargs="?", default="1h", help="30m, 2h, 1d (default 1h)")

    chat = command("chat", "manage the group whitelist; it lives in the ignored local config", cmd_chat)
    chat_kind = chat.add_subparsers(dest="chat_action", required=True)
    for name in ("add", "remove"):
        change = chat_kind.add_parser(name)
        change.add_argument("chat_id")
        change.set_defaults(func=cmd_chat)
    chat_kind.add_parser("list").set_defaults(func=cmd_chat)

    task = command("tasks", "the host session's side of semantic work", cmd_tasks)
    task_kind = task.add_subparsers(dest="tasks_action", required=True)
    waiting = task_kind.add_parser("wait", help="block until semantic tasks are ready")
    waiting.add_argument("--timeout", type=float, default=0.0, help="give up after this many seconds; 0 waits")
    waiting.set_defaults(func=cmd_tasks)
    card = task_kind.add_parser("card", help="print a task's read-only execution card")
    card.add_argument("--task", required=True)
    card.set_defaults(func=cmd_tasks)
    apply_output = task_kind.add_parser("apply", help="validate and accept a task's output")
    apply_output.add_argument("--task", required=True)
    apply_output.add_argument("--output", help="output file to read; default is the task's reserved path")
    apply_output.set_defaults(func=cmd_tasks)

    search = command("search", "a host session's own search; what it returns may be cited", cmd_search)
    search.add_argument("--task", required=True)
    search.add_argument("query")

    review_command = command("review", "what the assistant decided about discussions, including its silences", cmd_review)
    review_command.add_argument("--days", type=int, default=7)
    review_command.add_argument("--act", choices=["none", "add", "review", "gap"], help="only decisions of this kind")

    stats_command = command("stats", "counts of dispositions, decisions, sends, searches and reports", cmd_stats)
    stats_command.add_argument("--days", type=int, default=7)

    report = command("report", "coverage gaps and notices sent to the owner", cmd_report)
    report_kind = report.add_subparsers(dest="report_action", required=True)
    owner = report_kind.add_parser("to", help="open the private channel to an owner once")
    owner.add_argument("open_id")
    owner.set_defaults(func=cmd_report)
    listing = report_kind.add_parser("list", help="reports of the last days")
    listing.add_argument("--days", type=int, default=7)
    listing.set_defaults(func=cmd_report)
    show = report_kind.add_parser("show", help="one report with its discussion")
    show.add_argument("id")
    show.set_defaults(func=cmd_report)
