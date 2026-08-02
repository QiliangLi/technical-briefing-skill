from pathlib import Path

from briefing_skill.rendering import Renderer


def test_visual_block_uses_card_relative_asset_path(tmp_path: Path) -> None:
    card_dir = tmp_path / "workspace" / "runs" / "run-1" / "cards"
    asset = tmp_path / "workspace" / "runs" / "run-1" / "visuals" / "charts" / "chart.png"
    card_dir.mkdir(parents=True)
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"png")
    renderer = Renderer(tmp_path, None, None)  # type: ignore[arg-type]

    block = renderer._visual_block({}, {"asset_path": str(asset.relative_to(tmp_path)), "visual_purpose": "证据图"}, card_dir)

    assert "src='../visuals/charts/chart.png'" in block
    assert "alt='证据图'" in block


class _PlanDB:
    def __init__(self, plan_path: str):
        self.plan_path = plan_path

    def fetchall(self, query, params):
        return [{"brief_item_id": "item-1", "visual_plan_path": self.plan_path}]


def test_persist_visual_plan_keeps_rasterized_asset_for_approval(tmp_path: Path) -> None:
    plan_path = "workspace/runs/run-1/visuals/plans/item-1.json"
    renderer = Renderer(tmp_path, None, _PlanDB(plan_path))  # type: ignore[arg-type]
    issue = {
        "items": [
            {
                "brief_item_id": "item-1",
                "visual_plan": {"visual_mode": "chart_redraw", "asset_path": "visuals/chart.png"},
            }
        ]
    }

    renderer._persist_visual_plans("issue-1", issue)

    persisted = (tmp_path / plan_path).read_text(encoding="utf-8")
    assert '"asset_path": "visuals/chart.png"' in persisted


def test_chart_render_script_fits_arbitrary_svg_without_clipping() -> None:
    script = Renderer._chart_render_script()

    assert "object-fit: contain" in script
    assert "pathToFileURL" in script
    assert "clip:" not in script
