from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import ConfigBundle
from .db import Database
from .utils import read_json, write_json


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
        validator = self.root / "vendor" / "guizang-social-card-skill" / "validate-social-deck.mjs"
        report: dict[str, Any] = {"vendor_validator": False, "passes": [], "warnings": [], "failures": []}
        if validator.exists() and (run_dir / "cards" / "index.html").exists():
            proc = subprocess.run(["node", str(validator), str(run_dir / "cards")], cwd=self.root, text=True, capture_output=True)
            report["vendor_validator"] = True
            report["stdout"] = proc.stdout
            report["stderr"] = proc.stderr
            if proc.returncode:
                report["failures"].append("Guizang validator returned non-zero status")
            else:
                report["passes"].append("Guizang social-card validator passed")
        issue = self.db.fetchone("SELECT * FROM issues WHERE run_id=?", (run_id,))
        if issue and issue.get("issue_json_path"):
            data = read_json(self.root / issue["issue_json_path"])
            if 1 <= len(data.get("items", [])) <= 6:
                report["passes"].append("Issue item count is within 1-6")
            else:
                report["failures"].append("Issue item count exceeds configured maximum")
            for item in data.get("items", []):
                text = "".join(str(item.get(k, "")) for k in ("core_conclusion", "mechanism", "result", "boundary", "project_relevance"))
                if len(text) < 250:
                    report["warnings"].append(f"Item may be too short: {item.get('title')}")
                if not item.get("sources"):
                    report["failures"].append(f"Missing sources: {item.get('title')}")
        write_json(run_dir / "validation.json", report)
        return report
