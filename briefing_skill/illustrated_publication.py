from __future__ import annotations

import html as html_lib
from pathlib import Path
from typing import Any

from .utils import now_iso, read_json, write_json


TASK_TYPE = "illustrated_publication"
MANIFEST_RELATIVE_PATH = Path("illustrations") / "manifest.json"


def _is_remote_asset(value: str) -> bool:
    return value.startswith(("http://", "https://", "data:", "cid:"))


def _asset_src(root: Path, value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if _is_remote_asset(raw):
        return raw
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return None
    # Absolute local paths keep archived HTML directly previewable. The existing
    # send path rewrites them to CID parts before transport.
    return str(path.resolve())


def _illustration_row(item: dict[str, Any], src: str, index: int) -> str:
    alt = html_lib.escape(str(item.get("alt") or item.get("concept_name") or "技术解释图"), quote=True)
    caption = html_lib.escape(str(item.get("caption") or ""), quote=False)
    concept = html_lib.escape(str(item.get("concept_name") or f"illustration-{index}"), quote=True)
    persona = "1" if bool(item.get("persona_used")) else "0"
    return (
        f'<tr data-reader-role="explanatory-illustration" data-illustration-concept="{concept}" '
        f'data-persona-used="{persona}"><td class="pad-x" style="padding:8px 28px 18px">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="background:#fff;border:1px solid #d2d2cc"><tr><td align="center" '
        'style="padding:0;text-align:center">'
        f'<img alt="{alt}" src="{html_lib.escape(src, quote=True)}" '
        'style="display:block;width:100%;max-width:664px;height:auto;border:0;margin:0 auto" width="664"/>'
        '</td></tr>'
        + (
            '<tr><td style="padding:9px 12px 10px;background:#f0f1ed;border-top:1px solid #deded8;'
            'font-size:12px;line-height:1.5;color:#444"><b style="color:#002fa7">读图</b>　'
            f'{caption}</td></tr>'
            if caption
            else ""
        )
        + '</table></td></tr>'
    )


def render_illustrated_html(root: Path, base_html: str, manifest: dict[str, Any]) -> str:
    """Add generated issue-level explanatory images to the final base email.

    The base publication remains untouched. Missing/failed assets are skipped, so the
    illustrated artifact deterministically degrades to the exact baseline HTML. A
    generated image is rendered only when it satisfies the production invariant that
    the approved personal technical-scout IP is present.
    """

    prepared: list[tuple[int, dict[str, Any], str]] = []
    for index, item in enumerate(manifest.get("illustrations") or [], 1):
        if str(item.get("status") or "") != "generated":
            continue
        if item.get("persona_used") is not True:
            continue
        src = _asset_src(root, item.get("generated_asset_path"))
        if src:
            prepared.append((index, item, src))
    if not prepared:
        return base_html

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(base_html, "html.parser")
    after_judgements_target = None
    judgements = soup.select('table[data-reader-role="judgement"]')
    if judgements:
        after_judgements_target = judgements[-1].find_parent("tr")

    for index, item, src in prepared:
        fragment = BeautifulSoup(_illustration_row(item, src, index), "html.parser").find("tr")
        if fragment is None:
            continue

        placement = str(item.get("placement") or "after_judgements")
        topic_id = str(item.get("topic_id") or "").strip()
        inserted = False
        if placement == "before_topic" and topic_id:
            anchor = soup.find("a", id=f"topic-{topic_id}")
            topic_row = anchor.find_parent("tr") if anchor is not None else None
            if topic_row is not None:
                topic_row.insert_before(fragment)
                inserted = True
        if not inserted and after_judgements_target is not None:
            after_judgements_target.insert_after(fragment)
            after_judgements_target = fragment
            inserted = True
        if not inserted:
            body = soup.body
            if body is not None:
                body.append(fragment)

    return str(soup)


def build_illustrated_email(service, run_id: str, base_path: Path) -> Path:
    run_dir = service.root / "workspace" / "runs" / run_id
    manifest = read_json(run_dir / MANIFEST_RELATIVE_PATH, {"status": "fallback_to_text", "illustrations": []})
    illustrated = render_illustrated_html(
        service.root,
        base_path.read_text(encoding="utf-8"),
        manifest,
    )
    path = run_dir / "email-illustrated.html"
    path.write_text(illustrated, encoding="utf-8")
    return path


def _illustration_input(pipeline, issue: dict[str, Any]) -> dict[str, Any]:
    rows = pipeline.db.fetchall(
        """
        SELECT ii.position,ii.item_role,bi.id AS brief_item_id,bi.json_path,
               e.topic_id,e.direction_id
        FROM issue_items ii
        JOIN brief_items bi ON bi.id=ii.brief_item_id
        JOIN events e ON e.id=bi.event_id
        WHERE ii.issue_id=?
        ORDER BY ii.position
        """,
        (issue["id"],),
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        item = read_json(pipeline.root / row["json_path"], {})
        items.append(
            {
                "brief_item_id": row["brief_item_id"],
                "item_role": row.get("item_role") or "core",
                "topic_id": row["topic_id"],
                "direction_id": row["direction_id"],
                "title": item.get("title"),
                "core_conclusion": item.get("core_conclusion"),
                "mechanism": item.get("mechanism"),
                "result": item.get("result") or item.get("evidence_summary"),
                "boundary": item.get("boundary"),
                "project_relevance": item.get("project_relevance"),
            }
        )
    visuals = dict(pipeline.config.settings.get("visuals") or {})
    return {
        "issue_id": issue["id"],
        "synthesis": read_json(pipeline.root / issue["synthesis_path"], {}),
        "items": items,
        "constraints": {
            "illustration_count_policy": "no_fixed_cap; create every distinct explanatory image that materially improves understanding, without decorative or near-duplicate filler",
            "persona_required_for_generated_images": True,
            "aspect_ratio": "1.9:1",
            "persona_spec_path": "assets/persona/persona-spec.yaml",
            "persona_reference_path": visuals.get("persona_reference", "assets/persona/reference.jpg"),
            "approved_persona_asset_directories": ["pics/圆框形象", "pics/方框形象"],
            "output_directory": str((pipeline.run_dir / "illustrations").relative_to(pipeline.root)),
            "base_email_name": "email.html",
            "illustrated_email_name": "email-illustrated.html",
        },
    }


def install_illustrated_publication() -> None:
    """Make the verified issue-level illustrated email a mandatory second artifact.

    This deliberately replaces the unverified per-item visual-routing execution path
    for the active workflow. One Agent pass chooses every distinct explanatory image
    that materially improves the issue, with no fixed numeric cap. Every generated
    image must incorporate the approved personal technical-scout IP as a secondary,
    professional participant. Rendering always preserves email.html and also writes
    email-illustrated.html; failed image generation only removes images, never text.
    """

    from . import demo
    from .emailer import EmailService
    from .pipeline import Pipeline

    if getattr(Pipeline, "_illustrated_publication_installed", False):
        return

    original_apply = Pipeline._apply_task

    def apply_task(self, task: dict[str, Any]) -> None:
        if task["task_type"] != TASK_TYPE:
            return original_apply(self, task)
        output = self.tasks.read_result(task)
        path = self.run_dir / MANIFEST_RELATIVE_PATH
        write_json(path, output)

    Pipeline._apply_task = apply_task

    def prepare_illustrations(self) -> None:
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (self.run_id,))
        if not issue or not issue.get("synthesis_path"):
            return
        if self.db.fetchone(
            "SELECT 1 FROM tasks WHERE run_id=? AND task_type=? AND entity_id=?",
            (self.run_id, TASK_TYPE, issue["id"]),
        ):
            return
        self.tasks.create(
            self.run_id,
            TASK_TYPE,
            issue["id"],
            _illustration_input(self, issue),
            prompt="illustrated-publication.md",
            schema="illustrated-publication.schema.json",
            priority=95,
        )
        self.db.update_run(self.run_id, stage="AWAITING_ILLUSTRATIONS")

    # Supersede the old per-item materialisation/illustration-brief stage. The
    # active publication contract is one issue-level pass, matching the workflow
    # already validated in the committed illustrated briefing.
    Pipeline._maybe_prepare_illustrations = prepare_illustrations

    original_finalize = Pipeline._maybe_finalize_issue

    def finalize_issue(self) -> None:
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (self.run_id,))
        if issue and issue.get("synthesis_path"):
            task = self.db.fetchone(
                "SELECT * FROM tasks WHERE run_id=? AND task_type=? AND entity_id=?",
                (self.run_id, TASK_TYPE, issue["id"]),
            )
            if not task:
                self._maybe_prepare_illustrations()
                return
            if task.get("status") != "APPLIED":
                return
            manifest_path = self.run_dir / MANIFEST_RELATIVE_PATH
            if not manifest_path.is_file():
                return
        return original_finalize(self)

    Pipeline._maybe_finalize_issue = finalize_issue

    original_build = EmailService.build

    def build(self, run_id: str, *args, **kwargs):
        base_path = original_build(self, run_id, *args, **kwargs)
        illustrated_path = build_illustrated_email(self, run_id, base_path)
        issue = self.db.fetchone("SELECT id FROM issues WHERE run_id=?", (run_id,))
        if issue:
            self.db.execute(
                "UPDATE issues SET email_path=?,updated_at=? WHERE id=?",
                (str(illustrated_path.relative_to(self.root)), now_iso(), issue["id"]),
            )
        return illustrated_path

    EmailService.build = build

    original_demo_output = demo._demo_output

    def demo_output(task_type: str, data: dict[str, Any]):
        if task_type == TASK_TYPE:
            return {
                "status": "fallback_to_text",
                "illustrations": [],
                "notes": [
                    "Offline demo validates the mandatory dual-HTML publication contract without invoking image generation."
                ],
            }
        return original_demo_output(task_type, data)

    demo._demo_output = demo_output
    Pipeline._illustrated_publication_installed = True
