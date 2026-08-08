from __future__ import annotations

from .safe_efficiency import exact_primary_version_key
from .utils import now_iso, read_json, stable_hash, write_json


def install_primary_fulltext_cache() -> None:
    """Extend raw-text reuse to promoted immutable primaries from discovery feeds.

    The base safe-efficiency layer already caches sources accepted by the facts-cache
    eligibility policy. This wrapper handles the remaining case where a discovery
    adapter (for example AI HOT) has been deterministically promoted to an explicit
    immutable arXiv/GitHub primary version but still retains its discovery `source_id`.

    Facts remain context-aware and are not shared by this cache.
    """

    from .deep_efficiency import _cache_eligible
    from .fulltext import FulltextService

    if getattr(FulltextService, "_primary_fulltext_cache_installed", False):
        return

    original_fetch = FulltextService._fetch

    def fetch(self, url: str, raw: dict):
        # The inner safe-efficiency fetch already handles native immutable sources.
        if _cache_eligible(raw):
            return original_fetch(self, url, raw)

        version_key = exact_primary_version_key(raw)
        if not version_key:
            return original_fetch(self, url, raw)

        root = self.run_dir.parents[2]
        cache_key = stable_hash("primary-raw-fulltext-v1", version_key, length=32)
        cache_dir = root / "workspace" / "cache" / "fulltext"
        text_path = cache_dir / f"primary-{cache_key}.md"
        meta_path = cache_dir / f"primary-{cache_key}.json"
        if text_path.is_file() and meta_path.is_file():
            metadata = read_json(meta_path, {})
            text = text_path.read_text(encoding="utf-8")
            if text:
                self._raw_fulltext_cache_hit = True
                self._raw_fulltext_cache_key = f"primary:{cache_key}"
                return text, str(metadata.get("media_type") or "text/plain")

        text, media_type = original_fetch(self, url, raw)
        max_chars = int(self.config.settings.get("max_fulltext_chars", 140000))
        cached_text = self._sanitize_text(text)[:max_chars]
        cache_dir.mkdir(parents=True, exist_ok=True)
        text_path.write_text(cached_text, encoding="utf-8")
        write_json(
            meta_path,
            {
                "cache_key": cache_key,
                "primary_version_key": version_key,
                "source_identity": raw.get("identity_key"),
                "source_url": url,
                "media_type": media_type,
                "char_count": len(cached_text),
                "created_at": now_iso(),
            },
        )
        self._raw_fulltext_cache_key = f"primary:{cache_key}"
        return cached_text, media_type

    FulltextService._fetch = fetch
    FulltextService._primary_fulltext_cache_installed = True
