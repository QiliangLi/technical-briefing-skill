from __future__ import annotations

import html
import json
import logging
from pathlib import Path
from typing import Any

from .http import HttpClient
from .utils import read_json, write_json

LOGGER = logging.getLogger(__name__)


class VisualAssetService:
    def __init__(self, root: Path, run_dir: Path, timeout: float = 25):
        self.root = root
        self.run_dir = run_dir
        self.http = HttpClient(timeout=timeout)

    def close(self) -> None:
        self.http.close()

    def materialize(self, brief_item_id: str, plan_path: Path) -> dict[str, Any]:
        plan = read_json(plan_path, {})
        mode = plan.get("visual_mode")
        if mode == "chart_redraw" and plan.get("chart_data"):
            asset = self._render_svg_chart(brief_item_id, plan["chart_data"])
            plan["asset_path"] = str(asset.relative_to(self.root))
            write_json(plan_path, plan)
        elif mode in {"source_figure", "official_image", "screenshot"} and plan.get("source_asset_url") and not plan.get("asset_path"):
            try:
                asset = self._download_image(brief_item_id, plan["source_asset_url"])
                plan["asset_path"] = str(asset.relative_to(self.root))
                write_json(plan_path, plan)
            except Exception as exc:
                LOGGER.warning("Visual asset download failed %s: %s", plan.get("source_asset_url"), exc)
                plan.setdefault("warnings", []).append(f"asset download failed: {exc}")
                write_json(plan_path, plan)
        return plan

    def _download_image(self, brief_item_id: str, url: str) -> Path:
        response = self.http.get(url)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif", "image/svg+xml": ".svg"}
        ext = ext_map.get(content_type)
        if not ext:
            raise ValueError(f"URL is not a supported image: {content_type}")
        path = self.run_dir / "visuals" / "source" / f"{brief_item_id}{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        return path

    def _render_svg_chart(self, brief_item_id: str, data: dict[str, Any]) -> Path:
        labels = [str(x) for x in data.get("labels", [])]
        values = [float(x) for x in data.get("values", [])]
        if not labels or len(labels) != len(values):
            raise ValueError("chart_data requires equal non-empty labels and values")
        width, height = 936, 500
        margin_left, margin_right, margin_top, margin_bottom = 210, 90, 72, 54
        plot_w = width - margin_left - margin_right
        row_h = max(42, (height - margin_top - margin_bottom) / len(labels))
        max_value = max(values) or 1
        unit = html.escape(str(data.get("unit", "")))
        title = html.escape(str(data.get("title", "")))
        rows = []
        for idx, (label, value) in enumerate(zip(labels, values)):
            y = margin_top + idx * row_h + row_h * 0.18
            bar_h = row_h * 0.52
            bar_w = plot_w * value / max_value
            rows.append(
                f'<text x="{margin_left-18}" y="{y+bar_h*0.72:.1f}" text-anchor="end" class="label">{html.escape(label)}</text>'
                f'<rect x="{margin_left}" y="{y:.1f}" width="{plot_w:.1f}" height="{bar_h:.1f}" class="track"/>'
                f'<rect x="{margin_left}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" class="bar"/>'
                f'<text x="{margin_left+bar_w+12:.1f}" y="{y+bar_h*0.72:.1f}" class="value">{value:g}{unit}</text>'
            )
        note = html.escape(str(data.get("note", "")))
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
.bg{{fill:#f4f3ef}}.title{{font:500 30px Arial,'Microsoft YaHei',sans-serif;fill:#111}}.label{{font:500 20px Arial,'Microsoft YaHei',sans-serif;fill:#111}}.value{{font:700 18px Consolas,monospace;fill:#002fa7}}.track{{fill:#deded9}}.bar{{fill:#002fa7}}.note{{font:15px Arial,'Microsoft YaHei',sans-serif;fill:#666}}
</style><rect width="100%" height="100%" class="bg"/><text x="36" y="43" class="title">{title}</text>{''.join(rows)}<text x="36" y="{height-20}" class="note">{note}</text></svg>'''
        path = self.run_dir / "visuals" / "charts" / f"{brief_item_id}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")
        return path
