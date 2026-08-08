from __future__ import annotations

import threading
import time

from briefing_skill.adapters.base import CollectedItem
from briefing_skill.collection import MAX_COLLECTION_WORKERS, bounded_collection_workers, run_collectors_bounded


def _item(name: str) -> CollectedItem:
    return CollectedItem(
        source_id=name,
        discovery_source=name,
        source_level="A",
        discovery_only=False,
        title=name,
        original_url=f"https://example.com/{name}",
    )


def test_bounded_collection_overlaps_lanes_but_preserves_declared_order():
    second_started = threading.Event()

    class SlowFirst:
        def collect(self):
            if not second_started.wait(timeout=1.0):
                raise RuntimeError("second collector did not overlap")
            time.sleep(0.02)
            return [_item("first")]

    class FastSecond:
        def collect(self):
            second_started.set()
            return [_item("second")]

    runs = run_collectors_bounded([SlowFirst(), FastSecond()], max_workers=2)

    assert [run.error for run in runs] == [None, None]
    assert [[item.title for item in run.items] for run in runs] == [["first"], ["second"]]


def test_bounded_collection_isolates_one_collector_failure():
    class Broken:
        def collect(self):
            raise ValueError("boom")

    class Healthy:
        def collect(self):
            return [_item("healthy")]

    runs = run_collectors_bounded([Broken(), Healthy()], max_workers=2)

    assert runs[0].items == []
    assert runs[0].error == "ValueError: boom"
    assert [item.title for item in runs[1].items] == ["healthy"]
    assert runs[1].error is None


def test_collection_worker_count_is_strictly_bounded():
    assert bounded_collection_workers(0, 6) == 1
    assert bounded_collection_workers(3, 6) == 3
    assert bounded_collection_workers(99, 99) == MAX_COLLECTION_WORKERS
    assert bounded_collection_workers(3, 0) == 1
