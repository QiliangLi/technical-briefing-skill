from __future__ import annotations

from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Install briefing quality, coverage, and cost-control policies."""

    from .balanced_evidence import install_balanced_evidence
    from .cache_fastpath import install_fact_cache_fastpath
    from .cost_schema import install_cost_schema
    from .coverage_policy import install_coverage_policy
    from .deep_efficiency import install_deep_efficiency
    from .deep_eligibility import install_deep_eligibility_contract
    from .deep_eligibility_demo import install_deep_eligibility_demo
    from .deep_eligibility_version import install_deep_eligibility_cache_version
    from .deep_selection_contract import install_deep_selection_contract
    from .deep_selection_guard import install_deep_selection_guard
    from .editorial_batch import install_editorial_batching
    from .efficiency import install_pipeline_optimizations
    from .evidence_repair import install_evidence_repair
    from .execution_envelope import install_execution_envelope_contract
    from .executor_usage import install_executor_usage_telemetry
    from .final_reader_contract import install_final_reader_contract
    from .historical_backfill import install_historical_backfill
    from .human_feedback import install_human_feedback_telemetry
    from .invalid_repair import install_invalid_targeted_repair
    from .primary_fulltext_cache import install_primary_fulltext_cache
    from .project_insight import install_project_insight_layer
    from .quality_guard import install_quality_guards
    from .radar_signal_synthesis import install_radar_signal_synthesis
    from .radar_taxonomy import install_radar_taxonomy
    from .reader_facing_quality import install_reader_facing_quality
    from .reader_writing_contract import install_reader_writing_contract
    from .release_family import install_release_family_aggregation
    from .relevance_efficiency import install_relevance_efficiency
    from .safe_efficiency import install_safe_efficiency
    from .safe_efficiency_stats import install_safe_efficiency_stats
    from .session_grouping import install_session_grouping
    from .technology_value import install_technology_value_assessment
    from .telemetry import install_task_telemetry
    from .topic_appendix_render import install_topic_appendix_rendering
    from .topic_local_deep import install_topic_local_deep_policy
    from .value_scoring import install_value_scoring

    install_cost_schema()
    install_pipeline_optimizations()
    # Install before coverage_policy so its prepare_relevance wrapper first
    # materialises the rolling backlog and only then enters the cache fast path.
    install_relevance_efficiency()
    install_radar_taxonomy()
    install_quality_guards()
    install_coverage_policy()
    install_release_family_aggregation()
    install_topic_appendix_rendering()
    install_value_scoring()
    # This layer must precede deep-efficiency so its raw-fulltext cache becomes
    # the underlying fetch path captured by the context-aware Evidence wrapper.
    install_safe_efficiency()
    # Extend the same raw-text reuse to discovery records that were deterministically
    # promoted to an explicit immutable primary version while retaining source_id.
    install_primary_fulltext_cache()
    install_deep_efficiency()
    install_task_telemetry()
    install_fact_cache_fastpath()
    install_evidence_repair()
    install_editorial_batching()
    # Install after the existing CLI extensions so the backfill parser preserves
    # commands such as `stats`, while the wrapped `run` gets a small auto budget.
    install_historical_backfill()
    # Session grouping changes task-dispatch instructions and stats only.
    install_session_grouping()
    # INVALID repair is last in the task-dispatch chain so repairable fact tasks are
    # isolated from session grouping and receive the small sidecar path.
    install_invalid_targeted_repair()
    # Preserve all quality-neutral efficiency counters first, then append technology
    # value, project-insight, and finally human-review telemetry.
    install_safe_efficiency_stats()
    # Contract changes must invalidate both relevance and Technology Value cache keys,
    # even when prompt/schema text happens to stay unchanged.
    install_deep_eligibility_cache_version()
    install_technology_value_assessment()
    # Deep admission is now derived by Python from structured topic fit + Technology
    # Value. Install immediately after Technology Value so later selection only sees
    # candidates that passed the deterministic eligibility contract.
    install_deep_eligibility_contract()
    install_deep_eligibility_demo()
    install_project_insight_layer()
    install_human_feedback_telemetry()
    # Close the last deep-selection bypass after Technology Value has patched the
    # selector. Deep candidates must be assessed before high rule scores can compete.
    install_deep_selection_guard()
    # Product policy: every deep topic independently gets its own ranked Top4. This
    # must install after the Technology Value guard so ranking semantics stay intact,
    # while fetch failures refill from the same topic instead of another topic.
    install_topic_local_deep_policy()
    # Fail closed around the product meaning of that Top4: only genuine Deep-tail
    # candidates may enter the topic appendix, and final validation rechecks it.
    install_deep_selection_contract()
    # Rebalance the same 18k first-read budget across context/mechanism/results/bounds.
    # This must run after evidence-repair so cache versions include both policies.
    install_balanced_evidence()
    # Reader-facing guards merge project impact into 本期判断 and remove internal metadata.
    install_reader_facing_quality()
    # Reuse the existing issue-synthesis Agent to turn broad Radar candidates into
    # concrete technical signals.
    install_radar_signal_synthesis()
    # Reader-facing prose is a product contract, not a prompt preference: reject
    # title/conclusion repetition, generic filler, and verbose/numeric-heavy judgements.
    install_reader_writing_contract()
    # Final rendering is independently checked: no internal scores, no duplicate
    # Deep/appendix/Radar sources, no half-width orphan cards, and no invalid prose.
    install_final_reader_contract()
    # Install after every task-shaping wrapper so the outermost Host sees only the
    # canonical bound envelope, including grouped Fact dispatch.
    install_execution_envelope_contract()
    # Install last so `stats` sees every preceding telemetry wrapper. Executor usage
    # remains optional; without imported transcripts the existing proxies still work.
    install_executor_usage_telemetry()
    from .cli import main as cli_main

    return int(cli_main(list(argv) if argv is not None else None))