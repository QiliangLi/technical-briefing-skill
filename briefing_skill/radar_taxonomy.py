from __future__ import annotations

from typing import Any


STORAGE_MEDIA_TERMS = (
    "ssd",
    "nvme",
    "nand",
    "qlc",
    "tlc",
    "zns",
    "hdd",
    "persistent memory",
    "cxl memory",
    "hbm",
    "hbf",
    "high bandwidth flash",
    "high-bandwidth flash",
    "computational storage",
    "存储介质",
    "闪存",
    "持久内存",
    "高带宽闪存",
)

RADAR_CATEGORY_TERMS = (
    ("存储与介质", STORAGE_MEDIA_TERMS),
    (
        "KVCache生态",
        (
            "kv cache",
            "kvcache",
            "prefix cache",
            "lmcache",
            "cache-aware routing",
            "remote prefill",
            "prefill decode",
            "前缀缓存",
            "kv缓存",
        ),
    ),
    (
        "Agent生态",
        (
            "agent",
            "agentic",
            "harness",
            "agent harness",
            "coding harness",
            "agentic coding",
            "agentic workflow",
            "agentic system",
            "mcp",
            "computer use",
            "browser agent",
            "coding agent",
            "multi-agent",
            "agent memory",
            "tool call",
            "智能体",
        ),
    ),
    (
        "AI Infra",
        (
            "serving",
            "inference",
            "runtime",
            "compiler",
            "kernel",
            "gpu",
            "accelerator",
            "distributed training",
            "collective",
            "cluster",
            "observability",
            "interconnect",
            "fabric",
            "推理",
            "运行时",
            "编译器",
            "加速器",
            "集群",
            "互联",
        ),
    ),
)

HBF_QUERY = "High Bandwidth Flash HBF AI inference memory hierarchy"
HBF_ARXIV_TERMS = '(HBF OR "High Bandwidth Flash")'
HBF_INCLUDE_TERMS = (
    "hbf",
    "high bandwidth flash",
    "high-bandwidth flash",
    "高带宽闪存",
)


def classify_radar_category(title: str, summary: str) -> str:
    text = f" {title} {summary} ".lower()
    for name, terms in RADAR_CATEGORY_TERMS:
        if any(term in text for term in terms):
            return name
    return "其他"


def _append_unique(values: list[Any], additions: tuple[str, ...] | list[str]) -> None:
    existing = {str(value).strip().lower() for value in values}
    for addition in additions:
        if addition.lower() not in existing:
            values.append(addition)
            existing.add(addition.lower())


def augment_hbf_topic_queries(topics_config: dict[str, Any]) -> None:
    """Ensure HBF is both discoverable and classified as storage/media."""

    for topic in topics_config.get("topics") or []:
        if topic.get("id") != "ai_infra_horizontal":
            continue
        boost_terms = topic.setdefault("aihot_boost_terms", [])
        _append_unique(boost_terms, ["HBF", "High Bandwidth Flash"])
        for direction in topic.get("directions") or []:
            if direction.get("id") != "accelerator_memory_interconnect":
                continue
            queries = direction.setdefault("queries", [])
            _append_unique(queries, [HBF_QUERY])
            aihot_queries = direction.setdefault("aihot_queries", [])
            _append_unique(aihot_queries, ["HBF High Bandwidth Flash"])
            include_terms = direction.setdefault("include_terms", [])
            _append_unique(include_terms, list(HBF_INCLUDE_TERMS))
            arxiv_query = str(direction.get("arxiv_query") or "").strip()
            if "high bandwidth flash" not in arxiv_query.lower() and " hbf " not in f" {arxiv_query.lower()} ":
                direction["arxiv_query"] = (
                    f"({arxiv_query} OR {HBF_ARXIV_TERMS})" if arxiv_query else HBF_ARXIV_TERMS
                )
            return


def augment_agent_harness_queries(topics_config: dict[str, Any]) -> None:
    """Keep runtime-loaded topic variants aligned with the Agent Harness lane."""

    for topic in topics_config.get("topics") or []:
        if topic.get("id") != "agent_acceleration":
            continue
        _append_unique(
            topic.setdefault("aihot_boost_terms", []),
            [
                "harness",
                "agent harness",
                "coding harness",
                "agentic coding",
                "agentic workflow",
                "agentic system",
            ],
        )
        return


def install_radar_taxonomy() -> None:
    """Install the shared Radar taxonomy and augment HBF discovery queries."""

    from . import efficiency
    from .config import ConfigBundle

    efficiency.radar_category = classify_radar_category
    if getattr(ConfigBundle, "_radar_taxonomy_installed", False):
        return

    original_load = ConfigBundle.load.__func__

    def load(cls, paths):
        bundle = original_load(cls, paths)
        augment_hbf_topic_queries(bundle.topics)
        augment_agent_harness_queries(bundle.topics)
        return bundle

    ConfigBundle.load = classmethod(load)
    ConfigBundle._radar_taxonomy_installed = True
