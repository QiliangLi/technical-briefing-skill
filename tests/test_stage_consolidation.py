from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from briefing_skill.publication_stage import _accept_issue_level_illustrations


ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_uses_explicit_issue_and_publication_stages() -> None:
    source = (ROOT / "briefing_skill" / "bootstrap.py").read_text(encoding="utf-8")

    assert "install_issue_stage()" in source
    assert "install_publication_stage()" in source
    assert "install_topic_appendix_rendering()" not in source
    assert "install_reader_facing_quality()" not in source
    assert "install_final_reader_contract()" not in source
    assert source.index("install_issue_stage()") < source.index("install_illustrated_publication()")
    assert source.index("install_publication_stage()") < source.index("install_illustrated_publication()")


def test_new_issue_stage_creates_only_issue_synthesis_agent_work() -> None:
    source = (ROOT / "briefing_skill" / "issue_stage.py").read_text(encoding="utf-8")

    # The only TaskService.create call in the new path is issue_synthesis. Legacy task
    # names appear only in the resume detector and are never created by this stage.
    assert source.count("self.tasks.create(") == 1
    create_tail = source.split("self.tasks.create(", 1)[1]
    assert '"issue_synthesis"' in create_tail
    assert 'self.tasks.create(\n                    self.run_id,\n                    "visual_routing"' not in source
    assert 'self.tasks.create(\n                    self.run_id,\n                    "illustration_brief"' not in source


def test_project_insight_no_longer_patches_publication_or_validation() -> None:
    source = (ROOT / "briefing_skill" / "project_insight.py").read_text(encoding="utf-8")
    installer = source.split("def install_project_insight_layer", 1)[1]

    assert "EmailService.build" not in installer
    assert "Renderer.validate" not in installer
    assert "project_insights_required" in installer


def test_publication_stage_does_not_postprocess_built_html() -> None:
    source = (ROOT / "briefing_skill" / "publication_stage.py").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "email.html").read_text(encoding="utf-8")

    assert "EmailService.build =" not in source
    assert "normalise_orphan_card_widths" not in source
    assert 'data-source-title="1"' in template
    assert "{{ '100%' if single else '50%' }}" in template


def test_expanded_validator_allows_only_approved_issue_level_images(tmp_path: Path) -> None:
    valid = tmp_path / "valid.html"
    valid.write_text(
        '<html><body><table><tr data-reader-role="explanatory-illustration" '
        'data-persona-used="1"><td><img src="x.png"></td></tr></table></body></html>',
        encoding="utf-8",
    )

    class DB:
        def __init__(self, path: Path):
            self.path = path

        def fetchone(self, *_args, **_kwargs):
            return {"email_path": self.path.name}

    service = SimpleNamespace(root=tmp_path, db=DB(valid))
    report = {"failures": ["Expanded email must not contain item images"], "passes": []}
    _accept_issue_level_illustrations(service, "run", report)
    assert "Expanded email must not contain item images" not in report["failures"]
    assert any("approved issue-level explanatory illustrations" in value for value in report["passes"])

    invalid = tmp_path / "invalid.html"
    invalid.write_text('<html><body><img src="legacy.png"></body></html>', encoding="utf-8")
    service.db.path = invalid
    report = {"failures": ["Expanded email must not contain item images"], "passes": []}
    _accept_issue_level_illustrations(service, "run", report)
    assert "Expanded email must not contain item images" in report["failures"]
