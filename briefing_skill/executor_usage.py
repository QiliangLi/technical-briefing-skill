from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .utils import now_iso, stable_hash


EXECUTOR_USAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS executor_usage_records (
    record_key TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    executor TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_path TEXT NOT NULL,
    session_id TEXT,
    agent_id TEXT,
    request_id TEXT,
    message_id TEXT,
    model TEXT,
    timestamp TEXT,
    stage TEXT NOT NULL,
    task_ids_json TEXT NOT NULL DEFAULT '[]',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_input_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    is_error INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    imported_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_executor_usage_run
ON executor_usage_records(run_id, executor, source_kind, stage);

CREATE TABLE IF NOT EXISTS executor_usage_imports (
    import_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    executor TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    host_start TEXT,
    host_end TEXT,
    sources_json TEXT NOT NULL DEFAULT '[]',
    records_imported INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_executor_usage_import_run
ON executor_usage_imports(run_id, executor, imported_at);
"""


TASK_PATH_RE = re.compile(
    r"(?:workspace/runs/[^\s/'\"]+/)?tasks/(?P<task_type>[a-zA-Z0-9_-]+)/(?P<task_id>[a-fA-F0-9]{16,64})\.(?:input|output)\.json"
)
TASK_ID_RE = re.compile(r"\bTASK ID:\s*(?P<task_id>[a-fA-F0-9]{16,64})\b", re.I)
RUN_PATH_RE = re.compile(r"workspace/runs/(?P<run_id>[^/\s'\"]+)")


def ensure_executor_usage_schema(db) -> None:
    with db.connect() as conn:
        conn.executescript(EXECUTOR_USAGE_SCHEMA)


def _number(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _record_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    message = record.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    for key in ("text", "input", "content"):
                        value = item.get(key)
                        if isinstance(value, str):
                            parts.append(value)
                elif isinstance(item, str):
                    parts.append(item)
    attachment = record.get("attachment")
    if isinstance(attachment, dict):
        content = attachment.get("content")
        if isinstance(content, str):
            parts.append(content)
    return "\n".join(parts)


def _task_refs(text: str) -> tuple[set[str], dict[str, str], set[str]]:
    ids: set[str] = set()
    types: dict[str, str] = {}
    run_ids: set[str] = set()
    for match in TASK_PATH_RE.finditer(text):
        task_id = match.group("task_id")
        ids.add(task_id)
        types[task_id] = match.group("task_type")
    for match in TASK_ID_RE.finditer(text):
        ids.add(match.group("task_id"))
    for match in RUN_PATH_RE.finditer(text):
        run_ids.add(match.group("run_id"))
    return ids, types, run_ids


def _usage(record: dict[str, Any]) -> dict[str, int] | None:
    if record.get("type") != "assistant":
        return None
    message = record.get("message")
    if not isinstance(message, dict):
        return None
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None
    return {
        "input_tokens": _number(usage.get("input_tokens")),
        "cache_creation_input_tokens": _number(usage.get("cache_creation_input_tokens")),
        "cache_read_input_tokens": _number(usage.get("cache_read_input_tokens")),
        "output_tokens": _number(usage.get("output_tokens")),
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                # A transcript import is observational. One malformed line should not
                # discard all other valid API usage records from the same session.
                continue
            if isinstance(value, dict):
                value["_line_number"] = line_number
                rows.append(value)
    return rows


def _ancestor_context(
    record: dict[str, Any],
    by_uuid: dict[str, dict[str, Any]],
    *,
    max_hops: int = 24,
) -> str:
    """Return bounded causal context for task/stage attribution.

    We deliberately stop after a small parent chain instead of searching the whole
    transcript. A long host session may contain several briefing runs plus unrelated
    coding work; global text search would falsely attribute all later calls to the
    first run mentioned in the session.
    """

    parts = [_record_text(record)]
    parent = str(record.get("parentUuid") or "")
    hops = 0
    seen: set[str] = set()
    while parent and parent not in seen and hops < max_hops:
        seen.add(parent)
        row = by_uuid.get(parent)
        if not row:
            break
        text = _record_text(row)
        if text:
            parts.append(text)
        parent = str(row.get("parentUuid") or "")
        hops += 1
    return "\n".join(parts)


def _stage_from_context(
    context: str,
    task_type_by_id: dict[str, str],
    *,
    source_kind: str,
) -> tuple[str, list[str]]:
    task_ids, path_types, _ = _task_refs(context)
    resolved: dict[str, str] = {}
    for task_id in task_ids:
        task_type = task_type_by_id.get(task_id) or path_types.get(task_id)
        if task_type:
            resolved[task_id] = task_type
    types = sorted(set(resolved.values()))
    if len(types) == 1:
        return types[0], sorted(resolved)
    if len(types) > 1:
        return "mixed_agent_tasks" if source_kind == "agent" else "host_orchestration", sorted(resolved)

    lowered = context.lower()
    if source_kind == "host":
        if "briefing.py" in lowered or "workspace/runs/" in lowered:
            return "host_orchestration", []
        return "host_other", []
    return "unmapped_agent", []


def _safe_source_label(path: Path, root: Path | None) -> str:
    resolved = path.resolve()
    if root is not None:
        try:
            return str(resolved.relative_to(root.resolve()))
        except ValueError:
            pass
    return path.name


def parse_claude_code_usage_file(
    path: Path,
    *,
    run_id: str,
    task_type_by_id: dict[str, str] | None = None,
    source_kind: str = "agent",
    root: Path | None = None,
    host_start: datetime | None = None,
    host_end: datetime | None = None,
) -> list[dict[str, Any]]:
    """Parse Claude Code JSONL into provider-neutral token records.

    The four token counters are read exactly from ``message.usage``. Cache-creation
    and cache-read tokens are never folded into ordinary input, because the replay
    investigation specifically needs to distinguish those components.
    """

    rows = _load_jsonl(path)
    by_uuid = {
        str(row.get("uuid")): row
        for row in rows
        if row.get("uuid")
    }
    task_types = dict(task_type_by_id or {})

    # Subagent prompts often contain several compatible tasks in one session. Use the
    # whole source only to recover task IDs/types; usage still remains one session and
    # is never divided arbitrarily among those tasks.
    source_context = "\n".join(_record_text(row) for row in rows)
    source_task_ids, source_path_types, source_run_ids = _task_refs(source_context)
    for task_id, task_type in source_path_types.items():
        task_types.setdefault(task_id, task_type)

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        usage = _usage(row)
        if usage is None:
            continue
        timestamp = _parse_time(row.get("timestamp"))
        if source_kind == "host":
            if host_start is not None and (timestamp is None or timestamp < host_start):
                continue
            if host_end is not None and (timestamp is None or timestamp > host_end):
                continue

        context = _ancestor_context(row, by_uuid)
        stage, task_ids = _stage_from_context(context, task_types, source_kind=source_kind)
        if source_kind == "agent" and not task_ids:
            resolved_source_ids = [task_id for task_id in source_task_ids if task_id in task_types]
            task_ids = sorted(resolved_source_ids)
            source_types = sorted({task_types[task_id] for task_id in task_ids})
            if len(source_types) == 1:
                stage = source_types[0]
            elif len(source_types) > 1:
                stage = "mixed_agent_tasks"

        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        message_id = str(message.get("id") or "")
        request_id = str(row.get("requestId") or message.get("requestId") or "")
        event_identity = request_id or message_id or str(row.get("uuid") or row.get("_line_number"))
        key = stable_hash(
            "executor-usage-v1",
            source_kind,
            _safe_source_label(path, root),
            str(row.get("sessionId") or ""),
            event_identity,
            length=40,
        )
        item = {
            "record_key": key,
            "run_id": run_id,
            "executor": "claude-code",
            "source_kind": source_kind,
            "source_path": _safe_source_label(path, root),
            "session_id": str(row.get("sessionId") or ""),
            "agent_id": str(row.get("agentId") or ""),
            "request_id": request_id,
            "message_id": message_id,
            "model": str(message.get("model") or ""),
            "timestamp": str(row.get("timestamp") or ""),
            "stage": stage,
            "task_ids": task_ids,
            **usage,
            "is_error": int(bool(row.get("isApiErrorMessage") or row.get("error"))),
            "error_code": str(row.get("error") or row.get("apiErrorStatus") or ""),
        }
        # Some transcript formats can repeat one API response during streaming or
        # compaction. Keep the largest counters for one request/message identity
        # instead of double-billing the same response.
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = item
        else:
            for field in (
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
                "output_tokens",
            ):
                existing[field] = max(int(existing[field]), int(item[field]))
            existing["is_error"] = max(int(existing["is_error"]), int(item["is_error"]))

    # A subagent file explicitly imported for a run is accepted even if its prompt
    # omitted the run path. When it *does* name a different run, fail closed.
    if source_kind == "agent" and source_run_ids and run_id not in source_run_ids:
        return []
    return sorted(deduped.values(), key=lambda row: (row["timestamp"], row["record_key"]))


def _task_types_for_run(db, run_id: str) -> dict[str, str]:
    return {
        str(row["id"]): str(row["task_type"])
        for row in db.fetchall("SELECT id,task_type FROM tasks WHERE run_id=?", (run_id,))
    }


def _run_window(db, run_id: str) -> tuple[datetime | None, datetime | None]:
    row = db.fetchone("SELECT created_at,updated_at FROM runs WHERE id=?", (run_id,)) or {}
    return _parse_time(row.get("created_at")), _parse_time(row.get("updated_at"))


def import_executor_usage(
    db,
    root: Path,
    run_id: str,
    *,
    host_logs: Iterable[Path] = (),
    agent_logs: Iterable[Path] = (),
    executor: str = "claude-code",
    host_start: datetime | None = None,
    host_end: datetime | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    ensure_executor_usage_schema(db)
    if executor != "claude-code":
        raise ValueError(f"Unsupported executor adapter: {executor}")
    if replace:
        db.execute("DELETE FROM executor_usage_records WHERE run_id=? AND executor=?", (run_id, executor))
        db.execute("DELETE FROM executor_usage_imports WHERE run_id=? AND executor=?", (run_id, executor))

    default_start, default_end = _run_window(db, run_id)
    actual_start = host_start or default_start
    actual_end = host_end or default_end
    task_types = _task_types_for_run(db, run_id)

    sources: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for source_kind, paths in (("host", host_logs), ("agent", agent_logs)):
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(path)
            parsed = parse_claude_code_usage_file(
                path,
                run_id=run_id,
                task_type_by_id=task_types,
                source_kind=source_kind,
                root=root,
                host_start=actual_start if source_kind == "host" else None,
                host_end=actual_end if source_kind == "host" else None,
            )
            records.extend(parsed)
            sources.append(
                {
                    "kind": source_kind,
                    "path": _safe_source_label(path, root),
                    "usage_records": len(parsed),
                }
            )

    imported_at = now_iso()
    for row in records:
        db.execute(
            """
            INSERT INTO executor_usage_records(
                record_key,run_id,executor,source_kind,source_path,session_id,agent_id,
                request_id,message_id,model,timestamp,stage,task_ids_json,
                input_tokens,cache_creation_input_tokens,cache_read_input_tokens,
                output_tokens,is_error,error_code,imported_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(record_key) DO UPDATE SET
                stage=excluded.stage,
                task_ids_json=excluded.task_ids_json,
                input_tokens=excluded.input_tokens,
                cache_creation_input_tokens=excluded.cache_creation_input_tokens,
                cache_read_input_tokens=excluded.cache_read_input_tokens,
                output_tokens=excluded.output_tokens,
                is_error=excluded.is_error,
                error_code=excluded.error_code,
                imported_at=excluded.imported_at
            """,
            (
                row["record_key"], run_id, executor, row["source_kind"], row["source_path"],
                row["session_id"], row["agent_id"], row["request_id"], row["message_id"],
                row["model"], row["timestamp"], row["stage"],
                json.dumps(row["task_ids"], ensure_ascii=False),
                row["input_tokens"], row["cache_creation_input_tokens"],
                row["cache_read_input_tokens"], row["output_tokens"], row["is_error"],
                row["error_code"], imported_at,
            ),
        )

    import_id = stable_hash(
        "executor-usage-import-v1",
        run_id,
        executor,
        imported_at,
        json.dumps(sources, ensure_ascii=False, sort_keys=True),
        length=32,
    )
    db.execute(
        """
        INSERT INTO executor_usage_imports(
            import_id,run_id,executor,imported_at,host_start,host_end,sources_json,records_imported
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            import_id, run_id, executor, imported_at,
            actual_start.isoformat() if actual_start else None,
            actual_end.isoformat() if actual_end else None,
            json.dumps(sources, ensure_ascii=False), len(records),
        ),
    )
    return {
        "run_id": run_id,
        "executor": executor,
        "records_imported": len(records),
        "sources": sources,
        "host_window": {
            "start": actual_start.isoformat() if actual_start else None,
            "end": actual_end.isoformat() if actual_end else None,
            "source": "explicit" if host_start or host_end else "run_lifecycle",
        },
    }


def _sum_tokens(rows: Iterable[dict[str, Any]]) -> dict[str, int | float | None]:
    totals = {
        "input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 0,
    }
    count = 0
    for row in rows:
        count += 1
        for key in totals:
            totals[key] += _number(row.get(key))
    context = totals["input_tokens"] + totals["cache_creation_input_tokens"] + totals["cache_read_input_tokens"]
    total = context + totals["output_tokens"]
    cache = totals["cache_creation_input_tokens"] + totals["cache_read_input_tokens"]
    return {
        **totals,
        "context_input_tokens": context,
        "total_tokens": total,
        "cache_share_of_context": round(cache / context, 4) if context else None,
        "records": count,
    }


def executor_usage_stats(db, run_id: str, *, executor: str = "claude-code") -> dict[str, Any]:
    ensure_executor_usage_schema(db)
    rows = db.fetchall(
        """
        SELECT * FROM executor_usage_records
        WHERE run_id=? AND executor=?
        ORDER BY timestamp,record_key
        """,
        (run_id, executor),
    )
    if not rows:
        return {
            "available": False,
            "executor": executor,
            "note": "No executor transcript usage has been imported; pipeline character proxies are not token billing.",
        }

    by_scope: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_stage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_scope[str(row.get("source_kind") or "unknown")].append(row)
        by_stage[str(row.get("stage") or "unknown")].append(row)
        by_model[str(row.get("model") or "unknown")].append(row)

    # Retry attribution is session-level so a grouped agent that processed several
    # tasks is never divided into fictional per-task token shares.
    sessions: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("source_kind") != "agent":
            continue
        key = (
            str(row.get("source_path") or ""),
            str(row.get("session_id") or ""),
            str(row.get("agent_id") or ""),
        )
        sessions[key].append(row)
    ordered_sessions = sorted(
        sessions.values(),
        key=lambda group: min(str(row.get("timestamp") or "") for row in group),
    )
    seen_tasks: set[str] = set()
    retry_rows: list[dict[str, Any]] = []
    retry_sessions = 0
    for group in ordered_sessions:
        task_ids: set[str] = set()
        for row in group:
            try:
                task_ids.update(json.loads(row.get("task_ids_json") or "[]"))
            except (TypeError, json.JSONDecodeError):
                pass
        is_retry = bool(task_ids and task_ids & seen_tasks)
        if is_retry:
            retry_sessions += 1
            retry_rows.extend(group)
        seen_tasks.update(task_ids)

    latest_import = db.fetchone(
        """
        SELECT * FROM executor_usage_imports
        WHERE run_id=? AND executor=? ORDER BY imported_at DESC LIMIT 1
        """,
        (run_id, executor),
    ) or {}
    error_records = sum(int(row.get("is_error") or 0) for row in rows)
    return {
        "available": True,
        "executor": executor,
        "totals": _sum_tokens(rows),
        "by_scope": {key: _sum_tokens(value) for key, value in sorted(by_scope.items())},
        "by_stage": {key: _sum_tokens(value) for key, value in sorted(by_stage.items())},
        "by_model": {key: _sum_tokens(value) for key, value in sorted(by_model.items())},
        "agent_sessions": len(ordered_sessions),
        "retry": {
            "sessions": retry_sessions,
            "tokens": _sum_tokens(retry_rows),
            "definition": "an agent session references at least one task ID already seen in an earlier imported agent session",
        },
        "error_records": error_records,
        "host_window": {
            "start": latest_import.get("host_start"),
            "end": latest_import.get("host_end"),
        },
        "notes": [
            "Token counters come from executor message.usage records, not character-volume estimates.",
            "cache_creation_input_tokens and cache_read_input_tokens remain separate from ordinary input_tokens.",
            "Grouped multi-task agent sessions are attributed to a stage but are not arbitrarily split across individual tasks.",
            "Host records use the imported host time window; host turns without a task reference remain host_orchestration/host_other instead of receiving invented task attribution.",
            "total_tokens is a usage-volume sum, not a monetary bill; pricing and service tiers are intentionally outside this provider-neutral layer.",
        ],
    }


def _collect_agent_logs(directory: Path | None, explicit: Iterable[str]) -> list[Path]:
    paths = [Path(value).expanduser() for value in explicit]
    if directory is not None:
        paths.extend(sorted(directory.expanduser().glob("*.jsonl")))
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def _parse_cli_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = _parse_time(value)
    if parsed is None:
        raise argparse.ArgumentTypeError(f"Invalid ISO timestamp: {value}")
    return parsed


def install_executor_usage_telemetry() -> None:
    """Add transcript-token ingestion and append real usage to `stats`."""

    from . import cli, telemetry
    from .db import Database
    from .pipeline import Pipeline

    if getattr(Pipeline, "_executor_usage_telemetry_installed", False):
        return

    original_db_init = Database.init

    def db_init(self) -> None:
        original_db_init(self)
        ensure_executor_usage_schema(self)

    Database.init = db_init

    original_stats = telemetry.run_stats

    def run_stats(db, root: Path, run_id: str, *args, **kwargs):
        payload = original_stats(db, root, run_id, *args, **kwargs)
        payload["actual_token_usage"] = executor_usage_stats(db, run_id)
        return payload

    telemetry.run_stats = run_stats

    original_build_parser = cli.build_parser

    def cmd_import_usage(args) -> int:
        root, paths, config, db = cli._context(args)
        run_id = cli._resolve_run(db, args.run)
        host_logs = [Path(value).expanduser().resolve() for value in (args.host_log or [])]
        agent_logs = _collect_agent_logs(
            Path(args.subagent_dir) if args.subagent_dir else None,
            args.subagent_log or [],
        )
        if not host_logs and not agent_logs:
            raise SystemExit("import-usage requires --host-log, --subagent-log, or --subagent-dir")
        result = import_executor_usage(
            db,
            root,
            run_id,
            host_logs=host_logs,
            agent_logs=agent_logs,
            executor=args.executor,
            host_start=_parse_cli_time(args.host_start),
            host_end=_parse_cli_time(args.host_end),
            replace=bool(args.replace),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    def build_parser():
        parser = original_build_parser()
        subparsers = next(
            action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
        )
        p = subparsers.add_parser("import-usage")
        p.add_argument("--run", default="latest")
        p.add_argument("--executor", default="claude-code", choices=["claude-code"])
        p.add_argument("--host-log", action="append", default=[])
        p.add_argument("--subagent-log", action="append", default=[])
        p.add_argument("--subagent-dir")
        p.add_argument("--host-start", help="optional ISO timestamp overriding the run lifecycle start")
        p.add_argument("--host-end", help="optional ISO timestamp overriding the run lifecycle end")
        p.add_argument("--replace", action="store_true", help="replace prior imported usage for this run/executor")
        p.set_defaults(func=cmd_import_usage)
        return parser

    cli.build_parser = build_parser
    Pipeline._executor_usage_telemetry_installed = True
