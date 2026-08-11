from __future__ import annotations


def install_fact_cache_source_normalization() -> None:
    """Normalize source text, then install the two-level V2 read strategy.

    The raw-fulltext cache sits underneath FulltextService sanitization. Fact-cache V2
    reconstructs the final Evidence Pack from that raw cache, so it must apply the same
    sanitization first or exact Evidence hashes would miss despite identical source bytes.
    The L0/L1 lookup wrapper is installed only after this normalization hook is active.
    """

    from . import fact_cache_provenance
    from .fact_cache_two_level import install_two_level_fact_cache
    from .fulltext import FulltextService

    if getattr(fact_cache_provenance, "_source_normalization_installed", False):
        return
    original_cached_fulltext = fact_cache_provenance._cached_fulltext

    def cached_fulltext(root, run_dir, raw, fingerprint):
        text = original_cached_fulltext(root, run_dir, raw, fingerprint)
        if not text:
            return text
        return FulltextService._sanitize_text(text)

    fact_cache_provenance._cached_fulltext = cached_fulltext
    fact_cache_provenance._source_normalization_installed = True
    install_two_level_fact_cache()
