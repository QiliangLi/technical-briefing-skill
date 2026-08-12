from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from briefing_skill.business_time import briefing_date, briefing_now, briefing_timezone


def _config(name: str = "Asia/Shanghai"):
    return SimpleNamespace(settings={"timezone": name})


def test_shanghai_business_date_does_not_fall_back_to_previous_utc_day():
    # 2026-08-12 01:09 in Shanghai is still 2026-08-11 17:09 UTC.
    instant = datetime(2026, 8, 11, 17, 9, tzinfo=timezone.utc)
    assert briefing_now(_config(), instant).isoformat().startswith("2026-08-12T01:09")
    assert briefing_date(_config(), instant).isoformat() == "2026-08-12"


def test_business_date_respects_configured_timezone():
    instant = datetime(2026, 8, 11, 17, 9, tzinfo=timezone.utc)
    assert briefing_date(_config("UTC"), instant).isoformat() == "2026-08-11"


def test_invalid_configured_timezone_fails_closed():
    with pytest.raises(RuntimeError, match="Invalid timezone"):
        briefing_timezone(_config("Not/A-Timezone"))


def test_issue_and_discovery_business_dates_use_shared_helper():
    root = Path(__file__).resolve().parents[1]
    issue_source = (root / "briefing_skill" / "issue_stage.py").read_text(encoding="utf-8")
    discovery_source = (root / "briefing_skill" / "discovery_stage.py").read_text(encoding="utf-8")
    assert "briefing_date(" in issue_source
    assert "briefing_date(" in discovery_source
    assert "datetime.now(timezone.utc).date()" not in issue_source
    assert "datetime.now(timezone.utc).date()" not in discovery_source
