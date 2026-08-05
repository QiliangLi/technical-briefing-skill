from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import ConfigBundle, ConfigError
from .db import Database
from .utils import read_json, source_url_is_resolved, write_json


class Renderer:
    def __init__(self, root: Path, config: ConfigBundle, db: Database):
        self.root = root
        self.config = config
        self.db = db

    def render_issue(self, run_id: str, *, execute_playwright: bool = False) -> dict[str, Any]:
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
        if not issue or not issue.get("issue_json_path"):
            raise RuntimeError("Issue is not ready for rendering. Complete Agent tasks and run advance first.")
        run_dir = self.root / "workspace" / "runs" / run_id
        issue_data = read_json(self.root / issue["issue_json_path"])
        card_dir = run_dir / "cards"
        card_dir.mkdir(parents=True, exist_ok=True)
        if (issue_data.get("layout_mode") or self.config.settings.get("issue_mode")) == "expanded_v2":
            result = {
                "skipped": True,
                "reason": "expanded_v2 email is intentionally image-free",
                "output_dir": None,
                "rendered": False,
            }
            write_json(card_dir / "manifest.json", result)
            return result
        index_path = card_dir / "index.html"
        render_script = card_dir / "render.cjs"
        if execute_playwright:
            if self._render_svg_assets(issue_data, card_dir):
                write_json(self.root / issue["issue_json_path"], issue_data)
            # Also repair stale source plans from runs rendered before this
            # persistence rule was introduced.
            self._persist_visual_plans(issue["id"], issue_data)
        html_text = self._build_social_card_html(issue_data, card_dir)
        index_path.write_text(html_text, encoding="utf-8")
        render_script.write_text(self._render_script(), encoding="utf-8")
        result = {"index_html": str(index_path), "render_script": str(render_script), "output_dir": str(card_dir / "output")}
        if execute_playwright:
            subprocess.run(["node", str(render_script)], cwd=self.root, check=True)
            result["rendered"] = True
        else:
            result["rendered"] = False
        write_json(card_dir / "manifest.json", result)
        return result

    def _build_social_card_html(self, issue: dict[str, Any], card_dir: Path) -> str:
        upstream = self.root / "vendor" / "guizang-social-card-skill" / "assets" / "template-swiss-card.html"
        posters = [self._cover_section(issue)]
        for idx, item in enumerate(issue.get("items", []), 1):
            posters.append(self._item_section(item, idx, card_dir))
        posters.append(self._closing_section(issue))
        body = "\n".join(posters)
        fallback_path = self.root / "templates" / "social-card-fallback.html"
        fallback = fallback_path.read_text(encoding="utf-8")
        if upstream.exists():
            template = upstream.read_text(encoding="utf-8")
            # Keep the upstream Guizang typography/theme system, but replace every
            # seed/demo poster with this briefing's deterministic poster set.
            main_re = re.compile(r'<main\b[^>]*class=["\'][^"\']*sheet[^"\']*["\'][^>]*>.*?</main>', re.I | re.S)
            if main_re.search(template):
                template = main_re.sub(f'<main class="sheet">{body}</main>', template, count=1)
            elif "<!-- POSTERS_HERE -->" in template:
                template = template.replace("<!-- POSTERS_HERE -->", body, 1)
            else:
                template = template.replace("</body>", f'<main class="sheet">{body}</main></body>', 1)

            # The briefing-specific components are intentionally task-scoped.
            # Inject only the classes not guaranteed by the upstream seed, so a
            # future Guizang update does not silently remove our layout rules.
            fallback_style = re.search(r"<style>(.*?)</style>", fallback, re.S)
            if fallback_style:
                template = template.replace(
                    "</head>",
                    f"<style id=\"technical-briefing-components\">{fallback_style.group(1)}</style></head>",
                    1,
                )
            return template
        return fallback.replace("<!-- POSTERS_HERE -->", body)

    def _cover_section(self, issue: dict[str, Any]) -> str:
        synthesis = issue.get("synthesis", {})
        topics = " · ".join(synthesis.get("topic_names") or sorted({item.get("topic_name", item.get("topic_id", "")) for item in issue.get("items", [])}))
        return f"""
<section class="poster wide brief-cover" id="issue-cover" data-accent="ikb">
  <div class="content stack gap-7">
    <div class="chrome-min"><span class="t-cat">TECHNICAL BRIEFING · 技术情报</span><span class="t-meta">{html.escape(issue.get('date_from',''))} — {html.escape(issue.get('date_to',''))}</span></div>
    <h1 class="h-xl">技术情报简报</h1>
    <p class="lead">{html.escape(synthesis.get('headline') or '少量可信信息，支持项目判断')}</p>
    <div class="cover-metrics">
      <div><strong>{len(issue.get('items', []))}</strong><span>重点进展</span></div>
      <div><strong>{len(set(item.get('topic_id') for item in issue.get('items', [])))}</strong><span>覆盖专题</span></div>
      <div><strong>1 min</strong><span>单条阅读</span></div>
    </div>
    <div class="meta-strip">{html.escape(topics)}</div>
  </div>
</section>"""

    def _item_section(self, item: dict[str, Any], idx: int, card_dir: Path) -> str:
        plan = item.get("visual_plan") or {}
        visual = self._visual_block(item, plan, card_dir)
        keywords = " ".join(f"<span class='tag'>{html.escape(str(k))}</span>" for k in item.get("keywords", [])[:5])
        evidence = item.get("result") or item.get("evidence_summary") or ""
        return f"""
<section class="poster xhs brief-item" id="item-{idx:02d}" data-accent="ikb">
  <div class="content stack gap-5">
    <div class="chrome-min"><span class="t-cat">{html.escape(item.get('type','信息'))} · {html.escape(item.get('topic_name', item.get('topic_id','')))}</span><span class="t-meta">{html.escape(item.get('published_at',''))}</span></div>
    <h2 class="h-xl">{html.escape(item.get('title',''))}</h2>
    <p class="lead">{html.escape(item.get('core_conclusion',''))}</p>
    {visual}
    <div class="three-points">
      <div><span>机制</span><p>{html.escape(item.get('mechanism',''))}</p></div>
      <div><span>证据</span><p>{html.escape(evidence)}</p></div>
      <div><span>启发</span><p>{html.escape(item.get('project_relevance',''))}</p></div>
    </div>
    <div class="tag-row">{keywords}</div>
    <div class="meta-strip">{html.escape((item.get('sources') or [{}])[0].get('publisher',''))} · {html.escape((item.get('sources') or [{}])[0].get('url',''))}</div>
  </div>
</section>"""

    def _visual_block(self, item: dict[str, Any], plan: dict[str, Any], card_dir: Path) -> str:
        asset = (item.get("illustration") or {}).get("generated_asset_path") or plan.get("asset_path")
        if asset:
            path = Path(asset)
            if not path.is_absolute():
                path = self.root / asset
            if path.exists():
                try:
                    src = os.path.relpath(path, card_dir).replace("\\", "/")
                except Exception:
                    src = path.as_uri()
                return f"<figure class='visual-well'><img src='{html.escape(src)}' alt='{html.escape(plan.get('visual_purpose','技术配图'))}'></figure>"
        mode = plan.get("visual_mode", "text_only")
        labels = plan.get("labels") or []
        nodes = "".join(f"<div class='diagram-node'>{html.escape(str(label))}</div>" for label in labels[:5])
        return f"<div class='visual-placeholder'><span>{html.escape(mode)}</span><div class='node-row'>{nodes}</div></div>"

    def _render_svg_assets(self, issue: dict[str, Any], card_dir: Path) -> bool:
        assets: list[dict[str, str | int]] = []
        plans: list[tuple[dict[str, Any], Path]] = []
        for item in issue.get("items", []):
            plan = item.get("visual_plan") or {}
            asset = (item.get("illustration") or {}).get("generated_asset_path") or plan.get("asset_path")
            if not asset:
                continue
            source = Path(asset)
            if not source.is_absolute():
                source = self.root / source
            if source.suffix.lower() != ".svg" or not source.exists():
                continue
            target = source.with_suffix(".png")
            assets.append({"source": str(source.resolve()), "target": str(target.resolve()), "width": 936, "height": 500})
            plans.append((plan, target))
        if not assets:
            return False

        manifest = card_dir / "chart-assets.json"
        script = card_dir / "render-charts.cjs"
        write_json(manifest, assets)
        script.write_text(self._chart_render_script(), encoding="utf-8")
        subprocess.run(["node", str(script), str(manifest)], cwd=self.root, check=True)
        for plan, target in plans:
            if not target.exists():
                raise RuntimeError(f"Chart PNG was not generated: {target}")
            plan["asset_path"] = str(target.relative_to(self.root))
        return True

    def _persist_visual_plans(self, issue_id: str, issue: dict[str, Any]) -> None:
        """Keep approval/rebuild inputs aligned with rasterized issue assets."""
        plan_paths = {
            row["brief_item_id"]: row["visual_plan_path"]
            for row in self.db.fetchall(
                "SELECT brief_item_id, visual_plan_path FROM issue_items WHERE issue_id=?",
                (issue_id,),
            )
            if row.get("visual_plan_path")
        }
        for item in issue.get("items", []):
            brief_item_id = item.get("brief_item_id")
            plan_path = plan_paths.get(brief_item_id)
            plan = item.get("visual_plan")
            if plan_path and isinstance(plan, dict):
                write_json(self.root / plan_path, plan)

    @staticmethod
    def _chart_render_script() -> str:
        return r'''const { chromium } = require('playwright');
const fs = require('fs');
const { pathToFileURL } = require('url');
(async () => {
  const assets = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch({ headless: true });
  for (const asset of assets) {
    const page = await browser.newPage({ viewport: { width: asset.width, height: asset.height }, deviceScaleFactor: 1 });
    const sourceUrl = pathToFileURL(asset.source).href;
    await page.setContent(`<!doctype html><html><head><style>
      html, body { width: 100%; height: 100%; margin: 0; background: white; overflow: hidden; }
      img { width: 100%; height: 100%; display: block; object-fit: contain; object-position: center; }
    </style></head><body><img id="source" src="${sourceUrl}"></body></html>`);
    await page.waitForFunction(() => {
      const image = document.getElementById('source');
      return image && image.complete && image.naturalWidth > 0;
    });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: asset.target, omitBackground: false });
    await page.close();
  }
  await browser.close();
})();
'''

    def _closing_section(self, issue: dict[str, Any]) -> str:
        judgements = issue.get("synthesis", {}).get("judgements") or []
        rows = "".join(f"<div class='ledger-row'><b>{idx:02d}</b><p>{html.escape(str(judgement))}</p></div>" for idx, judgement in enumerate(judgements, 1))
        return f"""
<section class="poster xhs brief-closing" id="issue-closing" data-accent="ikb">
  <div class="content stack gap-7">
    <p class="t-cat">TAKEAWAYS · 本期判断</p>
    <h2 class="h-xl">值得继续追踪的<br>不是新闻，而是变化</h2>
    <div class="stacked-ledger">{rows}</div>
    <div class="meta-strip">Evidence first · Incremental only · Project oriented</div>
  </div>
</section>"""

    @staticmethod
    def _render_script() -> str:
        return r'''const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const base = __dirname;
  const out = path.join(base, 'output');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 2400, height: 1600 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(base, 'index.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(700);
  const nodes = await page.locator('.poster').all();
  for (let i = 0; i < nodes.length; i++) {
    const id = await nodes[i].getAttribute('id') || `poster-${i+1}`;
    await nodes[i].screenshot({ path: path.join(out, `${String(i+1).padStart(2,'0')}-${id}.png`) });
  }
  await browser.close();
})();
'''

    def validate(self, run_id: str) -> dict[str, Any]:
        run_dir = self.root / "workspace" / "runs" / run_id
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
        data: dict[str, Any] = {}
        mode = self.config.settings.get("issue_mode", "compact")
        if issue and issue.get("issue_json_path"):
            data = read_json(self.root / issue["issue_json_path"])
            mode = data.get("layout_mode") or mode
        validator = self.root / "vendor" / "guizang-social-card-skill" / "validate-social-deck.mjs"
        report: dict[str, Any] = {"vendor_validator": False, "passes": [], "warnings": [], "failures": []}
        if mode == "expanded_v2":
            self._validate_expanded_email(run_dir / "email.html", data, report)
        elif validator.exists() and (run_dir / "cards" / "index.html").exists():
            proc = subprocess.run(["node", str(validator), str(run_dir / "cards")], cwd=self.root, text=True, capture_output=True)
            report["vendor_validator"] = True
            report["stdout"] = proc.stdout
            report["stderr"] = proc.stderr
            if proc.returncode:
                report["failures"].append("Guizang validator returned non-zero status")
            else:
                report["passes"].append("Guizang social-card validator passed")
        if data:
            items = data.get("items", [])
            if mode == "expanded_v2":
                limits = {"core_min": 8, "core_max": 14, "observation_max": 4, "total_min": 12, "total_max": 18, "max_per_topic": 8, **self.config.scoring.get("expanded_v2", {})}
                core = data.get("core_items", [])
                observations = data.get("observations", [])
                topic_counts: dict[str, int] = {}
                for item in items:
                    topic_id = item.get("topic_id", "unknown")
                    topic_counts[topic_id] = topic_counts.get(topic_id, 0) + 1
                if len(items) > int(limits["total_max"]) or len(core) > int(limits["core_max"]) or len(observations) > int(limits["observation_max"]):
                    report["failures"].append("Expanded issue exceeds configured capacity")
                elif any(count > int(limits["max_per_topic"]) for count in topic_counts.values()):
                    report["failures"].append("Expanded issue exceeds per-topic capacity")
                else:
                    report["passes"].append("Expanded issue capacity is valid")
                if len(core) < int(limits["core_min"]) or len(items) < int(limits["total_min"]):
                    report["warnings"].append("Expanded issue is below its preferred minimum; do not add weak filler")
                for item in core:
                    score = float(item.get("score") or 0)
                    if score < float(limits["core_score"]):
                        report["failures"].append(f"Core item is below the core score threshold: {item.get('title')}")
                    if not any(source.get("source_level") == "A" for source in item.get("sources", [])):
                        report["failures"].append(f"Core item lacks an A-level source: {item.get('title')}")
                    if item.get("fact_check_status") != "PASS":
                        report["failures"].append(f"Core item did not pass fact checking: {item.get('title')}")
                for item in observations:
                    if item.get("item_role") != "observation":
                        report["failures"].append(f"Observation is not explicitly labelled: {item.get('title')}")
                    score = float(item.get("score") or 0)
                    if score < float(limits["observation_score"]):
                        report["failures"].append(f"Observation score is below the configured threshold: {item.get('title')}")
                    if item.get("fact_check_status") != "PASS":
                        report["failures"].append(f"Observation did not pass fact checking: {item.get('title')}")
            elif 1 <= len(items) <= 6:
                report["passes"].append("Compact issue item count is within 1-6")
            else:
                report["failures"].append("Compact issue item count exceeds configured maximum")
            for item in items:
                text = "".join(str(item.get(k, "")) for k in ("core_conclusion", "mechanism", "result", "boundary", "project_relevance"))
                if len(text) < 250:
                    report["warnings"].append(f"Item may be too short: {item.get('title')}")
                if not item.get("sources"):
                    report["failures"].append(f"Missing sources: {item.get('title')}")
                elif not any(
                    source.get("source_level") == "A" and source_url_is_resolved(source.get("url"))
                    for source in item.get("sources", [])
                ):
                    report["failures"].append(f"Missing resolved A-level source: {item.get('title')}")
                topic_id = item.get("topic_id")
                try:
                    expected_topic_name = self.config.topic(str(topic_id))["name"]
                except (ConfigError, KeyError, ValueError):
                    report["failures"].append(f"Unknown topic id {topic_id}: {item.get('title')}")
                else:
                    if item.get("topic_name") != expected_topic_name:
                        report["failures"].append(
                            f"Topic id/name mismatch: {item.get('title')} ({topic_id} != {item.get('topic_name')})"
                        )
                from .tasks import brief_item_validation_errors
                completeness_errors = brief_item_validation_errors(
                    item,
                    min_chars=int(self.config.settings.get("brief_item_min_chars", 300)),
                    max_chars=int(self.config.settings.get("brief_item_max_chars", 450)),
                )
                if completeness_errors:
                    report["failures"].append(
                        f"Incomplete or invalid item text: {item.get('title')} ({'; '.join(completeness_errors)})"
                    )
        write_json(run_dir / "validation.json", report)
        return report

    @staticmethod
    def _validate_expanded_email(email_path: Path, data: dict[str, Any], report: dict[str, Any]) -> None:
        """Validate the compact HTML deliverable instead of unused social-card PNGs."""
        if not email_path.exists():
            report["failures"].append("Expanded email HTML is missing")
            return
        email_html = email_path.read_text(encoding="utf-8")
        lower_html = email_html.lower()
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(email_html, "html.parser")
        visible_text = soup.get_text(" ", strip=True)
        if "<img" in lower_html:
            report["failures"].append("Expanded email must not contain item images")
        else:
            report["passes"].append("Expanded email contains no item images")

        missing_anchors = []
        for item in data.get("items", []):
            anchor = item.get("anchor_id") or f"item-{item.get('brief_item_id', '')}"
            if f'id="{html.escape(str(anchor), quote=True)}"' not in email_html:
                missing_anchors.append(str(anchor))
        if missing_anchors:
            report["failures"].append(f"Expanded email is missing item anchors: {', '.join(missing_anchors)}")
        else:
            report["passes"].append("Expanded email item anchors are complete")

        topic_ids = {str(item.get("topic_id", "unknown")) for item in data.get("items", [])}
        missing_topics = [topic_id for topic_id in sorted(topic_ids) if f'id="topic-{html.escape(topic_id, quote=True)}"' not in email_html]
        if missing_topics:
            report["failures"].append(f"Expanded email is missing topic groups: {', '.join(missing_topics)}")
        else:
            report["passes"].append("Expanded email topic groups are complete")

        if re.search(r"\bai\s*hot\b|\baihot\b", visible_text, flags=re.I):
            report["failures"].append("Expanded email exposes a forbidden discovery-source name")
        else:
            report["passes"].append("Expanded email does not expose discovery-source branding")
        forbidden_links = []
        for link in soup.find_all("a", href=True):
            hostname = (urlparse(str(link["href"])).hostname or "").lower().rstrip(".")
            if hostname == "aihot.virxact.com" or hostname.endswith(".aihot.virxact.com"):
                forbidden_links.append(str(link["href"]))
        if forbidden_links:
            report["failures"].append("Expanded email contains discovery-source links")
        else:
            report["passes"].append("Expanded email links only to accepted destinations")

        expected_title = "AI语义Fabric技术情报（内测版）"
        if expected_title not in visible_text or "TECHNICAL BRIEFING" not in visible_text:
            report["failures"].append("Expanded email header is incorrect")
        else:
            report["passes"].append("Expanded email header is correct")
        issue_date = str(data.get("date_to") or "")
        if issue_date and issue_date not in visible_text:
            report["failures"].append("Expanded email issue date is missing")
        if visible_text.count("阅读原文：") < len(data.get("items", [])):
            report["failures"].append("Expanded email is missing per-item original-source labels")
        else:
            report["passes"].append("Expanded email labels original-source links")

        judgement_ref_counts = [int(value) for value in re.findall(r'data-judgement-ref-count="(\d+)"', email_html)]
        expected_judgements = len(data.get("synthesis", {}).get("judgements") or [])
        if (
            "本期判断" not in email_html
            or len(judgement_ref_counts) != expected_judgements
            or any(count < 1 for count in judgement_ref_counts)
        ):
            report["failures"].append("Expanded email judgements lack concrete item references")
        else:
            report["passes"].append("Expanded email judgements expose concrete item references")
        if "热点雷达" not in visible_text or "未经本简报深度核验" not in visible_text:
            report["failures"].append("Expanded email hotspot radar or disclaimer is missing")
        else:
            report["passes"].append("Expanded email hotspot radar is clearly marked as discovery-only")
