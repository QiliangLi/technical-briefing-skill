from datetime import datetime, timezone

import pytest

from briefing_skill.cli import _run_id
from briefing_skill.config import ConfigBundle


def _config(timezone_name: str) -> ConfigBundle:
    return ConfigBundle(topics={}, sources={}, scoring={}, settings={"timezone": timezone_name}, email={})


def test_run_id_uses_configured_non_utc_plus_8_timezone():
    instant = datetime(2026, 1, 1, 1, 30, tzinfo=timezone.utc)
    assert _run_id(_config("America/Los_Angeles"), instant) == "2025-12-31-173000"


def test_run_id_rejects_invalid_timezone_clearly():
    with pytest.raises(RuntimeError, match="Invalid timezone in config/settings.yaml"):
        _run_id(_config("Not/A_Timezone"))
