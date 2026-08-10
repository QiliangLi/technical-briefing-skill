from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .cost_schema import ensure_cost_schema
from .utils import now_iso, read_json, stable_hash


DEFAULT_FACT_SESSION_GROUP_SIZE = 4
DEFAULT_FACT_SESSION_MAX_EVIDENCE_CHARS = 72000


def _number(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _task_input(root: Path, task: dict[str, Any]) -> dict[str, Any]:
    return read_json(root / str(task.get("input_path") or ""), {})


def _embedded_context_fingerprint(value: Any) -> str:
    try:
        encoded = json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return ""
    return stable_hash("fact-session-context-v1", encoded, length=20)


def _fact_group_key(task: dict[str, Any], data: dict[str, Any]) -> tuple[str, ...] | None:
    """Return a conservative execution-session key without changing task semantics.

    Fact extraction is independent per candidate. Compatible tasks may share one
    Agent invocation only when they use the same prompt/schema, the exact same topic
    context and project-context card. Direction remains task-local and is read from
    each input, so different directions inside one topic may share the invocation
    without sharing evidence, facts, outputs, cache state, or repair state.
    """

    if task.get("task_type") != "fact_extraction":
        return None
    document = data.get("document") or {}
    if document.get("fact_cache_hit"):
        return None
    topic = data.get("topic") or {}
    direction = data.get("direction") or {}
    topic_id = str(topic.get("id") or "")
    direction_id = str(direction.get("id") or "")
    context_path = str(data.get("project_context_path") or "")
    topic_fingerprint = _embedded_context_fingerprint(topic)
    direction_fingerprint = _embedded_context_fingerprint(direction)
    if (
        not topic_id
        or not direction_id
        or not context_path
        or not topic_fingerprint
        or not direction_fingerprint
    ):
        return None
    return (
        str(task.get("prompt_path") or ""),
        str(task.get("schema_path") or ""),
        topic_id,
        topic_fingerprint,
        context_path,
    )


def _evidence_chars(data: dict[str, Any]) -> int:
    document = data.get("document") or {}
    return max(
        0,
        _number(document.get("evidence_char_count") or document.get("char_count"), 0),
    )


def plan_fact_session_groups(
    root: Path,
    tasks: Iterable[dict[str, Any]],
    *,
    max_size: int = DEFAULT_FACT_SESSION_GROUP_SIZE,
    max_evidence_chars: int = DEFAULT_FACT_SESSION_MAX_EVIDENCE_CHARS,
) -> list[list[dict[str, Any]]]:
    """Plan quality-neutral Agent invocations for independent fact tasks.

    No task, Evidence Pack, prompt result, schema, cache entry, repair path, or
    downstream gate is merged. This planner only decides which compatible standalone
    tasks may be processed during one Agent invocation so startup/prompt/context cost
    is amortised. Each task still produces its own schema-bound output file.
    """

    size_limit = max(1, int(max_size))
    evidence_limit = max(4000, int(max_evidence_chars))
    ordered = sorted(
        [dict(task) for task in tasks if task.get("task_type") == "fact_extraction"],
        key=lambda task: (
            -float(task.get("priority") or 0),
            str(task.get("created_at") or ""),
            str(task.get("id") or ""),
        ),
    )

    groups: list[dict[str, Any]] = []
    open_group_by_key: dict[tuple[str, ...], int] = {}
    for task in ordered:
        data = _task_input(root, task)
        document = data.get("document") or {}
        key = _fact_group_key(task, data)
        if key is None:
            # Cache hits are synchronously applied before Agent dispatch. Any
            # malformed/legacy task that cannot prove compatibility remains alone.
            if not document.get("fact_cache_hit"):
                groups.append({"key": None, "tasks": [task], "evidence_chars": _evidence_chars(data)})
            continue

        evidence = _evidence_chars(data)
        if evidence <= 0:
            # Quality-first fail-closed rule: if the actual Evidence Pack size is
            # unknown, do not assume it is cheap enough to share a context window.
            groups.append({"key": None, "tasks": [task], "evidence_chars": 0})
            continue

        group_index = open_group_by_key.get(key)
        group = groups[group_index] if group_index is not None else None
        if (
            group is None
            or len(group["tasks"]) >= size_limit
            or group["evidence_chars"] + evidence > evidence_limit
        ):
            groups.append({"key": key, "tasks": [task], "evidence_chars": evidence})
            open_group_by_key[key] = len(groups) - 1
        else:
            group["tasks"].append(task)
            group["evidence_chars"] += evidence
            if len(group["tasks"]) >= size_limit:
                open_group_by_key.pop(key, None)

    groups.sort(
        key=lambda group: (
            -max(float(task.get("priority") or 0) for task in group["tasks"]),
            min(str(task.get("created_at") or "") for task in group["tasks"]),
        )
    )
    return [list(group["tasks"]) for group in groups]


def peek_execution_group(
    service,
    run_id: str,
    *,
    max_size: int = DEFAULT_FACT_SESSION_GROUP_SIZE,
    max_evidence_chars: int = DEFAULT_FACT_SESSION_MAX_EVIDENCE_CHARS,
) -> list[dict[str, Any]]:
    pending = service.db.fetchall(
        "SELECT * FROM tasks WHERE run_id=? AND status='PENDING' ORDER BY priority DESC, created_at",
        (run_id,),
    )
    if not pending:
        return []
    first = pending[0]
    if first.get("task_type") != "fact_extraction":
        return [first]

    groups = plan_fact_session_groups(
        service.root,
        pending,
        max_size=max_size,
        max_evidence_chars=max_evidence_chars,
    )
    first_id = str(first.get("id") or "")
    for group in groups:
        if any(str(task.get("id") or "") == first_id for task in group):
            return group
    # Conservative fallback for a legacy/cache task not eligible for grouping.
    return [first]


def fact_session_instructions(service, tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "No pending tasks"
    if len(tasks) == 1 or any(task.get("task_type") != "fact_extraction" for task in tasks):
        return service.instructions(tasks[0])

    first_input = _task_input(service.root, tasks[0])
    prompt_path = str(tasks[0]["prompt_path"])
    schema_path = str(tasks[0]["schema_path"])
    context_path = str(first_input.get("project_context_path") or "")
    topic = first_input.get("topic") or {}

    lines = [
        f"Fact-extraction execution batch: {len(tasks)} independent tasks in one Agent invocation",
        "This is an execution optimization only. Do NOT merge tasks, outputs, facts, directions, or evidence.",
        f"Shared topic: {topic.get('id', '')}",
        f"1. Read the shared prompt once: {prompt_path}",
        f"2. Read the shared result schema once: {schema_path}",
    ]
    step = 3
    if context_path:
        lines.append(f"{step}. Read the shared project-context card once: {context_path}")
        step += 1
    lines.extend(
        [
            f"{step}. Process the following tasks strictly one at a time, in order, within this same Agent invocation.",
            "   - For each task, read its own input JSON, including its own direction, and only the Evidence Pack/chunks referenced by that input.",
            "   - Evidence from an earlier task is inadmissible for every later task, even though the Agent invocation is shared.",
            "   - Apply the shared fact-extraction prompt independently to each source; never compare or synthesize the sources.",
            "   - Copy that task input's exact `_task` object into that task's output.",
            "   - Write a separate JSON output for every task; never return a combined array or batch file, and never reuse another task's facts.",
        ]
    )
    for index, task in enumerate(tasks, 1):
        data = _task_input(service.root, task)
        document = data.get("document") or {}
        direction = data.get("direction") or {}
        evidence_paths = document.get("chunks") or [document.get("text_path")]
        evidence_paths = [str(path) for path in evidence_paths if path]
        lines.extend(
            [
                f"   Task {index}: {task['id']} ({task['entity_id']})",
                f"     direction: {direction.get('id', '')}",
                f"     input:  {task['input_path']}",
                f"     evidence: {', '.join(evidence_paths)}",
                f"     output: {task['output_path']}",
            ]
        )
    lines.append(f"{step + 1}. After ALL outputs above are written, run exactly once: python3 briefing.py advance --run {tasks[0]['run_id']}")
    return "\n".join(lines)


def _mark_group_started(service, tasks: list[dict[str, Any]]) -> None:
    """Mirror telemetry's single-task attempt semantics for grouped CLI dispatch."""

    if not tasks:
        return
    ensure_cost_schema(service.db)
    for task in tasks:
        metric = service.db.fetchone("SELECT * FROM task_metrics WHERE task_id=?", (task["id"],))
        if not metric:
            continue
        last_started = metric.get("last_started_at")
        if last_started and str(last_started) >= str(task.get("updated_at") or ""):
            continue
        now = now_iso()
        service.db.execute(
            """
            UPDATE task_metrics
            SET attempts=attempts+1,
                first_started_at=COALESCE(first_started_at, ?),
                last_started_at=?
            WHERE task_id=?
            """,
            (now, now, task["id"]),
        )


def install_session_grouping() -> None:
    """Reuse one Agent invocation across compatible standalone fact tasks.

    The task graph and quality gates remain unchanged. Existing `tasks next` becomes
    batch-aware only at the CLI/instruction layer; `tasks next-single` is retained as
    an explicit compatibility/debug escape hatch.
    """

    from . import cli, telemetry
    from .pipeline import Pipeline
    from .tasks import TaskService

    if getattr(TaskService, "_session_grouping_installed", False):
        return

    original_advance = Pipeline.advance
    original_cmd_tasks = cli.cmd_tasks
    original_build_parser = cli.build_parser
    original_run_stats = telemetry.run_stats

    def limits(config) -> tuple[int, int]:
        policy = dict(config.settings.get("efficiency") or {})
        return (
            max(1, int(policy.get("fact_session_group_size", DEFAULT_FACT_SESSION_GROUP_SIZE))),
            max(4000, int(policy.get("fact_session_group_max_evidence_chars", DEFAULT_FACT_SESSION_MAX_EVIDENCE_CHARS))),
        )

    def peek_group(self, run_id: str, *, max_size: int, max_evidence_chars: int):
        return peek_execution_group(
            self,
            run_id,
            max_size=max_size,
            max_evidence_chars=max_evidence_chars,
        )

    def group_instructions(self, tasks: list[dict[str, Any]]) -> str:
        return fact_session_instructions(self, tasks)

    TaskService.peek_group = peek_group
    TaskService.group_instructions = group_instructions

    def advance(self):
        result = original_advance(self)
        max_size, max_chars = limits(self.config)
        group = self.tasks.peek_group(
            self.run_id,
            max_size=max_size,
            max_evidence_chars=max_chars,
        )
        result["next_task"] = self.tasks.group_instructions(group) if group else None
        return result

    def cmd_tasks(args) -> int:
        if args.action not in {"next", "next-single"}:
            return original_cmd_tasks(args)
        if args.action == "next-single":
            args.action = "next"
            try:
                return original_cmd_tasks(args)
            finally:
                args.action = "next-single"

        root, paths, config, db = cli._context(args)
        run_id = cli._resolve_run(db, args.run)
        service = TaskService(db, root, paths.runs / run_id)
        max_size, max_chars = limits(config)
        group = service.peek_group(
            run_id,
            max_size=max_size,
            max_evidence_chars=max_chars,
        )
        _mark_group_started(service, group)
        print(service.group_instructions(group))
        return 0

    def build_parser():
        parser = original_build_parser()
        subparsers = next(
            action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
        )
        tasks_parser = subparsers.choices.get("tasks")
        if tasks_parser is not None:
            action_arg = next((action for action in tasks_parser._actions if action.dest == "action"), None)
            if action_arg is not None and action_arg.choices is not None and "next-single" not in action_arg.choices:
                action_arg.choices = list(action_arg.choices) + ["next-single"]
        return parser

    def run_stats(db, root: Path, run_id: str, settings: dict[str, Any] | None = None):
        result = original_run_stats(db, root, run_id)
        actual_settings = settings
        if actual_settings is None:
            try:
                from .config import ConfigBundle
                from .paths import Paths

                actual_settings = ConfigBundle.load(Paths(root)).settings
            except Exception:
                # Stats must remain usable for isolated tests/diagnostics without a
                # complete repository config. Runtime dispatch still uses config.
                actual_settings = {}
        policy = dict((actual_settings or {}).get("efficiency") or {})
        max_size = max(1, int(policy.get("fact_session_group_size", DEFAULT_FACT_SESSION_GROUP_SIZE)))
        max_chars = max(4000, int(policy.get("fact_session_group_max_evidence_chars", DEFAULT_FACT_SESSION_MAX_EVIDENCE_CHARS)))
        tasks = db.fetchall(
            "SELECT * FROM tasks WHERE run_id=? AND task_type='fact_extraction' ORDER BY priority DESC, created_at",
            (run_id,),
        )
        groups = plan_fact_session_groups(
            root,
            tasks,
            max_size=max_size,
            max_evidence_chars=max_chars,
        )
        requiring_agent = sum(len(group) for group in groups)
        result["fact_session_plan"] = {
            "standalone_fact_tasks_requiring_agent": requiring_agent,
            "planned_agent_sessions": len(groups),
            "saved_agent_starts": max(0, requiring_agent - len(groups)),
            "group_size_limit": max_size,
            "group_evidence_char_limit": max_chars,
            "quality_guard": "same exact topic/project context; each task keeps its own direction/input/output/schema/evidence/cache/repair",
        }
        result.setdefault("notes", []).append(
            "fact_session_plan estimates host Agent invocations when `tasks next` batching is followed; it does not change the task count or evidence volume."
        )
        return result

    # telemetry's CLI stats callback resolves this module global at call time.
    telemetry.run_stats = run_stats
    Pipeline.advance = advance
    cli.cmd_tasks = cmd_tasks
    cli.build_parser = build_parser
    TaskService._session_grouping_installed = True
