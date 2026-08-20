from pathlib import Path

from briefing_skill.archive_reader import _reader_item
from briefing_skill.archive_reader_v2 import install_archive_reader_v2_persistence


ROOT = Path(__file__).resolve().parents[1]


def test_reader_item_preserves_v2_blocks() -> None:
    install_archive_reader_v2_persistence()
    item = {
        "topic_id": "tpn",
        "direction_id": "kv_transfer",
        "published_at": "2026-08-20",
        "score": 88.0,
        "sources": [],
    }
    prose = {
        "_provenance": {"source_item_hash": "0123456789abcdef"},
        "title": "测试标题",
        "blocks": [
            {"heading_key": None, "text": "先说发生了什么。"},
            {"heading_key": "mechanism", "text": "再解释它怎么实现。"},
        ],
        "lead": "先说发生了什么。",
        "body": ["再解释它怎么实现。"],
        "takeaway": None,
    }

    reader = _reader_item("core", item, prose)

    assert reader["blocks"] == prose["blocks"]
    assert reader["lead"] == prose["lead"]
    assert reader["body"] == prose["body"]


def test_rerender_pages_workflow_keeps_complete_site_and_safe_orphan_publish() -> None:
    source = (ROOT / ".github/workflows/rerender-archive-reader.yml").read_text(encoding="utf-8")

    assert "cp -R knowledge" in source
    assert "git clean -fdx" in source
    assert "git rm -rf ." not in source
    assert "briefing_skill/archive_reader_v2.py" in source
    assert "briefing_skill/reader_projection_v2.py" in source
    assert "schemas/archive-reader.schema.json" in source
