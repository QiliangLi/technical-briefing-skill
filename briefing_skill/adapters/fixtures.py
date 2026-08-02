from __future__ import annotations

from .base import CollectedItem


def offline_fixture_items() -> list[CollectedItem]:
    return [
        CollectedItem(
            source_id="fixture",
            discovery_source="Offline Fixture",
            source_level="A",
            discovery_only=False,
            title="CodeGraph reduces repeated repository exploration for coding agents",
            summary=(
                "A repository graph indexes symbols, files and call relationships before agent execution. "
                "The agent queries the graph to locate relevant code before using read and grep tools."
            ),
            original_url="https://example.com/codegraph-paper",
            published_at="2026-07-30T08:00:00Z",
            topic_hint="agent_acceleration",
            direction_hint="code_graph",
            priority=25,
            payload={"fixture": True},
        ),
        CollectedItem(
            source_id="fixture",
            discovery_source="Offline Fixture",
            source_level="A",
            discovery_only=False,
            title="KV cache aware scheduler coordinates prefill decode network bandwidth",
            summary=(
                "The system tracks KV cache location and decode urgency to allocate network bandwidth, "
                "reducing queueing for latency-sensitive inference requests."
            ),
            original_url="https://example.com/kv-network-paper",
            published_at="2026-07-29T08:00:00Z",
            topic_hint="tpn",
            direction_hint="kv_network_scheduling",
            priority=24,
            payload={"fixture": True},
        ),
    ]
