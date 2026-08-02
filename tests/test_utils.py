from briefing_skill.utils import canonicalize_url, title_similarity


def test_canonicalize_url_removes_tracking():
    assert canonicalize_url("HTTPS://Example.COM/a/?utm_source=x&id=1#frag") == "https://example.com/a?id=1"


def test_title_similarity():
    assert title_similarity("KV Cache Aware Network Scheduling", "KV cache-aware network scheduler") > 0.5
