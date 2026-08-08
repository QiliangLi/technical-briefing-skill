from __future__ import annotations

from briefing_skill.safe_efficiency_stats import collection_execution_metrics
from briefing_skill.utils import write_json


def test_collection_execution_metrics_reads_observed_worker_telemetry(tmp_path):
    run_id = "collection-stats"
    write_json(
        tmp_path / "workspace" / "runs" / run_id / "collection.json",
        {
            "execution": {
                "mode": "concurrent",
                "max_workers": 3,
                "wall_seconds": 4.2,
                "collectors": [
                    {"collector": "A", "count": 10, "duration_seconds": 4.0, "status": "OK", "error": None},
                    {"collector": "B", "count": 3, "duration_seconds": 1.5, "status": "OK", "error": None},
                    {"collector": "C", "count": 0, "duration_seconds": 0.8, "status": "ERROR", "error": "boom"},
                ],
            }
        },
    )

    metrics = collection_execution_metrics(tmp_path, run_id)

    assert metrics == {
        "mode": "concurrent",
        "max_workers": 3,
        "wall_seconds": 4.2,
        "collector_work_seconds": 6.3,
        "collector_failures": 1,
        "collector_counts": {"A": 10, "B": 3, "C": 0},
    }


def test_collection_execution_metrics_is_null_safe_for_old_runs(tmp_path):
    metrics = collection_execution_metrics(tmp_path, "missing")
    assert metrics["mode"] is None
    assert metrics["collector_counts"] == {}
