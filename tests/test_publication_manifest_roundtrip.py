from __future__ import annotations

import shutil
from pathlib import Path
from types import MethodType

from briefing_skill.emailer import EmailService
from briefing_skill.publication_manifest import (
    illustration_provenance_errors,
    publication_provenance_errors,
    write_publication_manifest,
)
from briefing_skill.utils import write_json


class _Config:
    email = {
        "subject_template": "AI语义Fabric技术情报（公测版）",
        "footer": "fixture footer",
    }
    # This suite exercises the legacy synthesized-radar roundtrip; direct-copy
    # provenance gates have their own dedicated tests.
    scoring = {"radar": {"direct_copy": False}}

    @staticmethod
    def topic_list():
        return [{"id": "topic-a", "name": "Topic A", "description": ""}]


class _DB:
    def __init__(self, issue: dict):
        self.issue = issue
        self.executed: list[tuple[str, tuple]] = []

    def fetchone(self, sql: str, args=()):
        if "FROM issues" in sql:
            return dict(self.issue)
        return None

    def execute(self, sql: str, args=()):
        self.executed.append((sql, tuple(args)))

    def update_run(self, run_id: str, **kwargs):
        return None


def _issue_data(run_id: str) -> dict:
    return {
        "id": "issue-roundtrip",
        "run_id": run_id,
        "date_from": "2026-08-13",
        "date_to": "2026-08-13",
        "synthesis": {"headline": "Round-trip fixture", "judgements": []},
        "items": [
            {
                "brief_item_id": "item-1",
                "item_role": "core",
                "topic_id": "topic-a",
                "topic_name": "Topic A",
                "direction_id": "direction-a",
                "direction_name": "Direction A",
                "type": "论文",
                "published_at": "2026-08-13",
                "title": "Manifest/template round-trip",
                "core_conclusion": "结论完整。",
                "mechanism": "机制完整。",
                "result": "证据完整。",
                "boundary": "边界完整。",
                "project_relevance": "启发完整。",
                "sources": [
                    {"publisher": "Source 1", "url": "https://example.org/source-1"},
                    {"publisher": "Source 2", "url": "https://example.org/source-2"},
                    {"publisher": "Source 3", "url": "https://example.org/source-3"},
                ],
            }
        ],
    }


def test_manifest_writer_round_trips_through_real_emailservice_template(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    (tmp_path / "templates").mkdir(parents=True)
    shutil.copy(repo_root / "templates" / "email.html", tmp_path / "templates" / "email.html")

    run_id = "roundtrip-run"
    issue_data = _issue_data(run_id)
    issue_path = tmp_path / "workspace" / "runs" / run_id / "issue.json"
    synthesis_path = tmp_path / "workspace" / "runs" / run_id / "synthesis.json"
    write_json(issue_path, issue_data)
    write_json(synthesis_path, issue_data["synthesis"])
    issue = {
        "id": issue_data["id"],
        "run_id": run_id,
        "issue_json_path": str(issue_path.relative_to(tmp_path)),
        "synthesis_path": str(synthesis_path.relative_to(tmp_path)),
    }

    service = EmailService(tmp_path, _Config(), _DB(issue))
    service._topic_appendix_cache = {}
    radar_groups = [
        {
            "name": "AI Infra",
            "items": [
                {
                    "title": "Current-run radar signal",
                    "summary": "Radar summary",
                    "url": "https://example.org/radar",
                    "source_name": "example.org",
                    "published_at": "2026-08-13",
                }
            ],
        }
    ]
    radar_contract = {
        "raw_eligible": 1,
        "legal_capacity": 1,
        "required_minimum": 1,
        "final_count": 1,
        "total_max": 8,
        "max_per_category": 2,
    }

    def _aihot_groups(self, issue_date=None, *, issue_id=None, issue_data=None):
        write_publication_manifest(self, issue_data, radar_groups, radar_contract)
        return radar_groups

    service._aihot_groups = MethodType(_aihot_groups, service)
    email_path = service.build(run_id)
    html = email_path.read_text(encoding="utf-8")

    assert publication_provenance_errors(tmp_path, run_id, html) == []
    assert "https://example.org/source-1" in html
    assert "https://example.org/source-2" in html
    assert "https://example.org/source-3" not in html
    assert "https://example.org/radar" in html


def test_illustration_provenance_counts_duplicate_rendered_images(tmp_path: Path):
    run_id = "illustration-duplicate"
    asset_url = "https://example.org/generated.png"
    write_json(
        tmp_path / "workspace" / "runs" / run_id / "illustrations" / "manifest.json",
        {
            "status": "complete",
            "illustrations": [
                {
                    "status": "generated",
                    "persona_used": True,
                    "published_asset_url": asset_url,
                }
            ],
        },
    )
    html = f"""
    <table>
      <tr data-reader-role="explanatory-illustration"><td><img src="{asset_url}"></td></tr>
      <tr><td>separating content</td></tr>
      <tr data-reader-role="explanatory-illustration"><td><img src="{asset_url}"></td></tr>
    </table>
    """

    errors = illustration_provenance_errors(tmp_path, run_id, html)
    assert any("including multiplicity" in error for error in errors)


def test_missing_illustration_manifest_can_be_required_by_caller(tmp_path: Path):
    errors = illustration_provenance_errors(
        tmp_path,
        "missing-manifest",
        "<html><body>text-only fallback</body></html>",
        required=True,
    )
    assert any("Missing illustrations/manifest.json" in error for error in errors)
