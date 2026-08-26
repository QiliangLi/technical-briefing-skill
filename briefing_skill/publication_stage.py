from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import write_json


def _attach_appendix_and_source_titles(service, groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from .reader_facing_quality import _source_title

    appendix = getattr(service, "_topic_appendix_cache", {}) or {}
    by_id = {str(group.get("id") or ""): group for group in groups}
    for topic in service.config.topic_list():
        topic_id = str(topic.get("id") or "")
        extra = list(appendix.get(topic_id) or [])
        if extra:
            group = by_id.get(topic_id)
            if group is None:
                group = {
                    "id": topic_id,
                    "name": topic.get("name") or topic_id,
                    "description": topic.get("description", ""),
                    "items": [],
                    "observations": [],
                    "total_count": 0,
                }
                groups.append(group)
                by_id[topic_id] = group
            group["appendix"] = extra
            group["appendix_count"] = len(extra)
            group["total_count"] = int(group.get("total_count") or 0) + len(extra)

    for group in groups:
        group.setdefault("appendix", [])
        group.setdefault("appendix_count", len(group["appendix"]))
        # The 论文/来源 line is reader provenance: floor-upgraded observations
        # need it exactly like native detailed cards.
        for item in [*(group.get("items") or []), *(group.get("observations") or [])]:
            if item.get("source_title") is None:
                item["source_title"] = _source_title(service, item)

    order = {
        str(topic.get("id") or ""): index
        for index, topic in enumerate(service.config.topic_list())
    }
    groups.sort(key=lambda group: order.get(str(group.get("id") or ""), len(order)))
    return groups


def _publication_quality_errors(service, run_id: str) -> list[str]:
    from .reader_facing_quality import FORBIDDEN_READER_PHRASES

    issue = service.db.fetchone("SELECT email_path FROM issues WHERE run_id=?", (run_id,))
    if not issue or not issue.get("email_path"):
        return ["PublicationValidator requires a persisted reader-facing email artifact"]
    path = service.root / issue["email_path"]
    if not path.is_file():
        return ["PublicationValidator cannot read the persisted email artifact"]
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if "data-project-insight-count=" in text or ">项目影响<" in text:
        errors.append("Project impact must be folded into 本期判断, not rendered as a separate section")
    leaked = [phrase for phrase in FORBIDDEN_READER_PHRASES if phrase.lower() in text.lower()]
    if leaked:
        errors.append(
            "Internal selection metadata leaked into reader output: "
            + ", ".join(sorted(set(leaked)))
        )
    return errors


def _accept_issue_level_illustrations(service, run_id: str, report: dict[str, Any]) -> None:
    """Replace the old expanded-mode blanket image ban with the new image contract."""

    legacy_failure = "Expanded email must not contain item images"
    if legacy_failure not in (report.get("failures") or []):
        return
    issue = service.db.fetchone("SELECT email_path FROM issues WHERE run_id=?", (run_id,))
    if not issue or not issue.get("email_path"):
        return
    path = service.root / issue["email_path"]
    if not path.is_file():
        return

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    images = soup.find_all("img")
    if not images:
        return
    for image in images:
        row = image.find_parent("tr", attrs={"data-reader-role": "explanatory-illustration"})
        if row is None or str(row.get("data-persona-used") or "") != "1":
            return

    report["failures"] = [
        failure for failure in report.get("failures") or [] if failure != legacy_failure
    ]
    report.setdefault("passes", []).append(
        "Expanded publication contains only approved issue-level explanatory illustrations"
    )


def _structured_provenance_errors(service, run_id: str) -> list[str]:
    from .publication_manifest import (
        illustration_provenance_errors,
        publication_provenance_errors,
    )

    issue = service.db.fetchone("SELECT email_path FROM issues WHERE run_id=?", (run_id,))
    if not issue or not issue.get("email_path"):
        return ["Structured provenance requires a persisted email artifact"]
    path = service.root / issue["email_path"]
    if not path.is_file():
        return ["Structured provenance cannot read the persisted email artifact"]
    html = path.read_text(encoding="utf-8")
    active = service.db.fetchone(
        """
        SELECT i.id, i.run_id, i.date_to, i.issue_json_path,
               rep.execution_mode
        FROM issues i
        LEFT JOIN run_execution_provenance rep ON rep.run_id=i.run_id
        WHERE i.run_id=?
        """,
        (run_id,),
    )
    return [
        *publication_provenance_errors(service.root, run_id, html, active_issue=active),
        *illustration_provenance_errors(service.root, run_id, html),
    ]


LEDGER_CONTENT_COLUMNS = (
    "run_id",
    "provider",
    "upstream_lane",
    "lane_key",
    "upstream_item_id",
    "upstream_story_id",
    "upstream_url",
    "original_url",
    "canonical_original_url",
    "title_hash",
    "summary_hash",
)

SUPPORTED_LEDGER_STATUS_SCHEMAS = {1}


def _upstream_ledger_errors(service, run_id: str) -> list[str]:
    """The internal upstream audit ledger must match the frozen input exactly.

    The sidecar is required for a frozen run and strictly validated; the
    database is then compared against the full expected audit projection in
    BOTH directions — missing rows, extra rows and rows whose content
    disagrees with the frozen observation (wrong provider/lane/identity or
    altered hashes/payload) all block the release.
    """
    import json as json_module

    from .adapters.aihot import expected_ledger_records
    from .utils import read_json

    base = service.root / "workspace" / "runs" / run_id / "source-cache" / "aihot"
    errors: list[str] = []

    freeze_path = base / "freeze.json"
    freeze = read_json(freeze_path, {}) if freeze_path.is_file() else {}
    if freeze and str(freeze.get("run_id") or "") != run_id:
        errors.append("frozen AI Hot input belongs to another run")

    expected = expected_ledger_records(freeze, run_id) if freeze else None

    status_path = base / "ledger-status.json"
    if expected is not None or status_path.is_file():
        # A frozen run MUST carry a status sidecar; absence, corruption,
        # foreign ownership or an unsupported schema is a hard failure.
        if not status_path.is_file():
            errors.append("AI Hot upstream ledger is incomplete: status sidecar is missing for a frozen run")
            status = None
        else:
            try:
                status = read_json(status_path, None)
            except (ValueError, json_module.JSONDecodeError):
                errors.append("AI Hot ledger status file is corrupt and cannot be verified")
                status = None
        if isinstance(status, dict):
            for field in ("schema", "run_id", "records_attempted", "last_error"):
                if field not in status:
                    errors.append(f"AI Hot ledger status is missing required field '{field}'")
            if status.get("run_id") is not None and str(status.get("run_id")) != run_id:
                errors.append("AI Hot ledger status belongs to another run")
            schema = status.get("schema")
            if isinstance(schema, int) is False or schema not in SUPPORTED_LEDGER_STATUS_SCHEMAS:
                errors.append(
                    f"AI Hot ledger status schema ({schema!r}) is not in the supported set "
                    f"{sorted(SUPPORTED_LEDGER_STATUS_SCHEMAS)}"
                )
            attempted = status.get("records_attempted")
            if not isinstance(attempted, int) or isinstance(attempted, bool) or attempted < 0:
                errors.append("AI Hot ledger status records_attempted must be a non-negative integer")
            elif expected is not None and attempted != len(expected):
                errors.append(
                    f"AI Hot ledger status records_attempted ({attempted}) does not match the "
                    f"{len(expected)} observations required by the frozen input"
                )
            if status.get("last_error"):
                errors.append("AI Hot upstream ledger is incomplete for this run: " + str(status.get("last_error")))
    elif freeze and freeze.get("ledger_error"):
        errors.append(
            "AI Hot upstream ledger is incomplete for this run: " + str(freeze.get("ledger_error"))
        )

    if expected is not None:
        rows = service.db.fetchall("SELECT * FROM radar_upstream_records WHERE run_id=?", (run_id,))
        actual = {str(row.get("record_id")): row for row in rows}
        missing = sorted(set(expected) - set(actual))
        extras = sorted(set(actual) - set(expected))
        if missing:
            errors.append(
                f"AI Hot upstream ledger DB is incomplete: {len(missing)} frozen observations "
                "are missing from radar_upstream_records"
            )
        if extras:
            errors.append(
                f"AI Hot upstream ledger DB has {len(extras)} records the frozen input does not "
                "explain (stale or foreign rows for this run)"
            )
        for record_id in sorted(set(expected) & set(actual)):
            row = actual[record_id]
            projection = expected[record_id]
            mismatches = [
                column
                for column in LEDGER_CONTENT_COLUMNS
                if (row.get(column) or None) != (projection.get(column) or None)
            ]
            raw_value = row.get("raw_payload_json")
            try:
                raw_sha = (
                    "sha256:"
                    + __import__("briefing_skill.utils", fromlist=["content_hash"]).content_hash(
                        json_module.dumps(json_module.loads(raw_value), ensure_ascii=False, sort_keys=True)
                    )
                    if raw_value
                    else None
                )
            except (TypeError, ValueError):
                raw_sha = None
            if raw_sha != projection.get("raw_payload_sha"):
                mismatches.append("raw_payload")
            if mismatches:
                errors.append(
                    f"AI Hot upstream ledger record {record_id} disagrees with the frozen input "
                    f"on {', '.join(mismatches)}"
                )
    return errors


def _public_upstream_trace_errors(service, run_id: str) -> list[str]:
    """Published artifacts must not expose the invisible upstream anywhere."""
    from .public_trace_scan import public_upstream_trace_errors, run_public_files

    issue = service.db.fetchone("SELECT email_path FROM issues WHERE run_id=?", (run_id,))
    email_paths: list[Path] = []
    if issue and issue.get("email_path"):
        email_paths.append(service.root / issue["email_path"])
    run_dir = service.root / "workspace" / "runs" / run_id
    baseline = run_dir / "email.html"
    if baseline not in email_paths:
        email_paths.append(baseline)
    return public_upstream_trace_errors(
        run_public_files(service.root, run_id, email_paths=email_paths)
    )


def install_publication_stage() -> None:
    """Own structured publication assembly and keep final validation mutation-free."""

    from . import coverage_policy
    from . import final_reader_contract
    from . import reader_facing_quality
    from .emailer import EmailService
    from .pipeline import Pipeline
    from .publication_manifest import (
        filter_current_final_radar_groups,
        finalize_radar_groups,
        write_publication_manifest,
    )
    from .rendering import Renderer

    if getattr(Pipeline, "_publication_stage_installed", False):
        return

    # Reader-writing contract is installed first, so this wraps its appendix cleaner
    # and then removes internal selection prose. The old string-HTML appendix path is
    # disabled; appendices are attached to topic groups and rendered once by Jinja.
    original_collect = coverage_policy.collect_topic_appendix

    def collect_topic_appendix(service, run_id: str, issue_data: dict[str, Any]):
        return reader_facing_quality._clean_topic_appendix(
            service,
            original_collect,
            run_id,
            issue_data,
        )

    coverage_policy.collect_topic_appendix = collect_topic_appendix
    coverage_policy._appendix_html = lambda _service, _appendix: ""

    original_topic_groups = EmailService._topic_groups

    def topic_groups(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        return _attach_appendix_and_source_titles(self, original_topic_groups(self, data))

    EmailService._topic_groups = topic_groups

    # Radar finalization happens after Deep + Appendix are fixed. Historical reference
    # issues are not allowed to refill Radar. Surviving Agent-selected signals are kept
    # first, then only this run's frozen reserve candidates may fill the product minimum.
    original_aihot_groups = EmailService._aihot_groups

    def aihot_groups(self, issue_date=None, *, issue_id=None, issue_data=None):
        groups = original_aihot_groups(
            self,
            issue_date,
            issue_id=issue_id,
            issue_data=issue_data,
        )
        if not issue_data:
            return groups
        filtered = filter_current_final_radar_groups(
            self,
            groups,
            issue_data=issue_data,
        )
        final_groups, contract = finalize_radar_groups(
            self,
            filtered,
            issue_id=str(issue_id) if issue_id else None,
            issue_data=issue_data,
        )
        write_publication_manifest(self, issue_data, final_groups, contract)
        return final_groups

    EmailService._aihot_groups = aihot_groups

    # Validation is now a pure observer. It may fail the release, but it never rewrites
    # the issue, Radar set, template output, card widths, source-title markup, or manifest.
    original_validate = Renderer.validate

    def validate(self, run_id: str):
        report = original_validate(self, run_id)
        _accept_issue_level_illustrations(self, run_id, report)
        failures = list(report.get("failures") or [])
        failures.extend(final_reader_contract.final_reader_contract_errors(self, run_id))
        failures.extend(_publication_quality_errors(self, run_id))
        failures.extend(_structured_provenance_errors(self, run_id))
        failures.extend(_public_upstream_trace_errors(self, run_id))
        failures.extend(_upstream_ledger_errors(self, run_id))
        report["failures"] = list(dict.fromkeys(failures))
        report["warnings"] = list(dict.fromkeys(report.get("warnings") or []))
        if report["failures"]:
            report["passes"] = list(dict.fromkeys(report.get("passes") or []))
        else:
            report.setdefault("passes", []).append(
                "Final publication satisfies structured selection, writing, layout, source and Radar contracts"
            )
            report.setdefault("passes", []).append(
                "Final HTML exactly matches the structured Deep/Appendix/Radar/illustration provenance"
            )
            report.setdefault("passes", []).append(
                "Project impact is merged into 本期判断 and internal selection metadata is hidden"
            )
            report["passes"] = list(dict.fromkeys(report.get("passes") or []))
        write_json(self.root / "workspace" / "runs" / run_id / "validation.json", report)
        return report

    Renderer.validate = validate
    Pipeline._publication_stage_installed = True
