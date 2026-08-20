from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from .reader_projection import reader_item_path
from .reader_projection_v2 import FIXED_BRIEFING_TITLE, HEADING_LABELS, normalise_blocks
from .utils import read_json


def _heading_tag(soup: BeautifulSoup, key: str):
    heading = soup.new_tag("div")
    heading["data-reader-section-heading"] = "1"
    heading["data-reader-section-role"] = key
    heading["style"] = (
        "font:700 11px/1.35 'Microsoft YaHei','微软雅黑',Arial,sans-serif;"
        "color:#5b6475;margin:9px 0 3px;letter-spacing:.1px"
    )
    heading.string = HEADING_LABELS[key]
    return heading


def _block_tag(
    soup: BeautifulSoup,
    *,
    text: str,
    index: int,
    observation: bool,
):
    paragraph = soup.new_tag("p")
    paragraph["data-reader-block"] = "1"
    paragraph["data-reader-block-index"] = str(index)
    if index == 0:
        color = "#444" if observation else "#333"
        paragraph["style"] = (
            f"font-size:13px;line-height:1.52;margin:0 0 8px;color:{color}"
        )
    else:
        paragraph["style"] = (
            "font-size:12px;line-height:1.52;margin:7px 0 0;color:#4a4a4a"
        )
    paragraph.string = text
    return paragraph


def render_blocks_native(
    html: str,
    readers: dict[str, dict[str, Any]],
    *,
    issue_date: str = "",
) -> str:
    """Replace legacy lead/body placeholders with the persisted v2 block sequence."""

    soup = BeautifulSoup(html, "html.parser")
    for item_id, reader in readers.items():
        blocks = normalise_blocks(reader.get("blocks"))
        if not blocks:
            continue
        node = soup.find(id=f"item-{item_id}")
        if node is None:
            continue

        for old in node.select('[data-reader-section-heading="1"]'):
            old.decompose()
        for paragraph in node.find_all("p", recursive=False):
            paragraph.decompose()

        source_links = next(
            (
                child
                for child in node.find_all("div", recursive=False)
                if child.get_text(" ", strip=True).startswith("阅读原文：")
            ),
            None,
        )
        if source_links is None:
            continue

        observation = node.find_parent(attrs={"data-reader-role": "observation-card"}) is not None
        for index, block in enumerate(blocks):
            key = block.get("heading_key")
            if key in HEADING_LABELS:
                source_links.insert_before(_heading_tag(soup, str(key)))
            source_links.insert_before(
                _block_tag(
                    soup,
                    text=str(block.get("text") or ""),
                    index=index,
                    observation=observation,
                )
            )

    for node in soup.find_all("div"):
        style = str(node.get("style") or "")
        if "display:none" in style and "max-height:0" in style:
            node.clear()
            node.append(
                f"{FIXED_BRIEFING_TITLE} · {issue_date}"
                if issue_date
                else FIXED_BRIEFING_TITLE
            )
            break
    return str(soup)


def install_reader_blocks_renderer_v2() -> None:
    """Make final current-run email HTML read directly from v2 sidecar blocks."""

    from .emailer import EmailService
    from .pipeline import Pipeline

    if getattr(Pipeline, "_reader_blocks_renderer_v2_installed", False):
        return

    original_build = EmailService.build

    def build(self, run_id: str, *, status_after: str = "AWAITING_APPROVAL"):
        path = original_build(self, run_id, status_after=status_after)
        if not path.is_file():
            return path
        issue_row = self.db.fetchone(
            "SELECT issue_json_path FROM issues WHERE run_id=?", (run_id,)
        ) or {}
        issue = (
            read_json(self.root / issue_row.get("issue_json_path", ""), {})
            if issue_row.get("issue_json_path")
            else {}
        )
        readers: dict[str, dict[str, Any]] = {}
        for item in [*(issue.get("core_items") or []), *(issue.get("observations") or [])]:
            item_id = str(item.get("brief_item_id") or "")
            if not item_id:
                continue
            sidecar = read_json(reader_item_path(self.root, run_id, item_id), {})
            if sidecar.get("blocks"):
                readers[item_id] = sidecar
        if readers:
            path.write_text(
                render_blocks_native(
                    path.read_text(encoding="utf-8"),
                    readers,
                    issue_date=str(issue.get("date_to") or ""),
                ),
                encoding="utf-8",
            )
        return path

    EmailService.build = build
    Pipeline._reader_blocks_renderer_v2_installed = True
