from pathlib import Path

from scripts.backfill_archive_provenance import ARCHIVE_DATES, validate_archives


ROOT = Path(__file__).resolve().parents[1]


def test_committed_historical_archives_have_complete_reader_provenance() -> None:
    assert validate_archives(ROOT) == []


def test_provenance_is_present_for_all_six_historical_issues() -> None:
    for issue_date in ARCHIVE_DATES:
        original = ROOT / "archive" / "issues" / issue_date / "original"
        assert (original / "reader.json").is_file()
        assert (original / "provenance.json").is_file()
        assert (original / "email-illustrated.html").is_file()
