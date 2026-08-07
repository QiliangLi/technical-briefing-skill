from briefing_skill.dedup import EventClusterer


def _row(*, topic="tpn", direction="kv_transfer", identity="", title="Same System", hint="Same System"):
    return {
        "topic_id": topic,
        "direction_id": direction,
        "identity_key": identity,
        "title": title,
        "event_hint": hint,
    }


def test_fuzzy_event_merge_requires_same_topic_and_direction():
    base = _row(identity="url:https://example.com/a")
    assert EventClusterer._same_event(base, _row(topic="cross_region", identity="url:https://example.com/b")) is False
    assert EventClusterer._same_event(base, _row(direction="pd_disaggregation", identity="url:https://example.com/b")) is False


def test_distinct_strong_identities_never_merge_only_because_titles_match():
    a = _row(identity="arxiv:2608.00001", title="Fast KV Transfer", hint="Fast KV Transfer")
    b = _row(identity="arxiv:2608.00002", title="Fast KV Transfer", hint="Fast KV Transfer")
    assert EventClusterer._same_event(a, b) is False


def test_same_strong_identity_merges_inside_same_context():
    a = _row(identity="doi:10.1145/123/456")
    b = _row(identity="doi:10.1145/123/456", title="A translated title")
    assert EventClusterer._same_event(a, b) is True
