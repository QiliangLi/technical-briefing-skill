from types import SimpleNamespace

from briefing_skill.value_scoring import value_aware_event_score


def _scorer(freshness: float = 0.4):
    return SimpleNamespace(_freshness=lambda raw: freshness)


def test_value_review_dominates_field_count_in_final_score():
    strong = value_aware_event_score(
        _scorer(),
        [{"quality_score": 85, "evidence": [{"value": "20%", "baseline": "baseline", "condition": "test"}]}],
        [{"relevance_score": 92}],
        [{"canonical_url": "https://arxiv.org/abs/1"}],
    )
    weak = value_aware_event_score(
        _scorer(1.0),
        [{"quality_score": 90, "mechanism": "filled", "limitations": "filled", "evidence": [{}, {}, {}]}],
        [{"relevance_score": 68}],
        [{"canonical_url": "https://github.com/example/repo/releases/tag/v1"}],
    )
    assert strong > weak
    assert strong >= 75


def test_final_score_rewards_specific_evidence_without_overriding_relevance():
    plain = value_aware_event_score(
        _scorer(),
        [{"quality_score": 80, "evidence": [{}]}],
        [{"relevance_score": 80}],
        [{"canonical_url": "https://example.com/a"}],
    )
    specific = value_aware_event_score(
        _scorer(),
        [{"quality_score": 80, "evidence": [{"value": "1.4x", "baseline": "A", "condition": "B"}]}],
        [{"relevance_score": 80}],
        [{"canonical_url": "https://example.com/a"}],
    )
    assert specific > plain
