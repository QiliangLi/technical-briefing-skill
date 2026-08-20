from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.migrate_historical_reader_v2 import ARCHIVE_DATES, migrate_archives


ROOT = Path(__file__).resolve().parents[1]


def test_all_committed_historical_readers_are_block_native_and_schema_valid() -> None:
    schema = json.loads((ROOT / "schemas/archive-reader.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    for issue_date in ARCHIVE_DATES:
        path = ROOT / "archive" / "issues" / issue_date / "reader.json"
        reader = json.loads(path.read_text(encoding="utf-8"))
        assert reader["rewrite_status"] == "historical_semantic_rewrite"
        assert not list(validator.iter_errors(reader)), issue_date
        assert reader["items"], issue_date

        for item_id, item in reader["items"].items():
            blocks = item.get("blocks") or []
            assert 1 <= len(blocks) <= 3, (issue_date, item_id)
            assert item["lead"] == blocks[0]["text"], (issue_date, item_id)
            assert item["body"] == [block["text"] for block in blocks[1:]], (issue_date, item_id)
            assert item["takeaway"] is None, (issue_date, item_id)
            assert blocks[0]["heading_key"] is None, (issue_date, item_id)


def test_historical_reader_v2_migration_is_idempotent() -> None:
    assert migrate_archives(ROOT, check=True) == []


def test_historical_rewrite_schema_rejects_missing_blocks() -> None:
    path = ROOT / "archive" / "issues" / ARCHIVE_DATES[0] / "reader.json"
    reader = json.loads(path.read_text(encoding="utf-8"))
    first_item = next(iter(reader["items"].values()))
    first_item.pop("blocks")

    schema = json.loads((ROOT / "schemas/archive-reader.schema.json").read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(reader))

    assert errors
    assert any("blocks" in error.message for error in errors)
