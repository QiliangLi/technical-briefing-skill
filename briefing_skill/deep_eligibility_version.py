from __future__ import annotations

import json

from .deep_eligibility import DEEP_ENTRY_CONTRACTS
from .utils import stable_hash


def contract_fingerprint(topic_id: str) -> str:
    contract = DEEP_ENTRY_CONTRACTS.get(str(topic_id or ""))
    if not contract:
        return "no-deep-contract"
    encoded = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return stable_hash("deep-entry-contract-v1", encoded, length=20)


def install_deep_eligibility_cache_version() -> None:
    """Invalidate semantic caches whenever the machine-readable Deep contract changes."""

    from . import relevance_efficiency

    if getattr(relevance_efficiency, "_deep_eligibility_cache_version_installed", False):
        return
    original_version = relevance_efficiency.relevance_evaluator_version

    def relevance_evaluator_version(config, root, topic_id, direction_id, published_at):
        base = original_version(config, root, topic_id, direction_id, published_at)
        return stable_hash(
            "relevance-plus-deep-contract-v1",
            base,
            contract_fingerprint(str(topic_id or "")),
            length=24,
        )

    relevance_efficiency.relevance_evaluator_version = relevance_evaluator_version
    relevance_efficiency._deep_eligibility_cache_version_installed = True
