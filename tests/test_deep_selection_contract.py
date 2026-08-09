from __future__ import annotations

from types import SimpleNamespace

from briefing_skill.deep_selection_contract import (
    _filter_deferred_appendix,
    appendix_candidate_is_deferred,
    render_deferred_appendix_row,
)


def _candidate(*, status: str, fulltext_required: int = 1, relevant: int = 1):
    return {
        "status": status,
        "fulltext_required": fulltext_required,
        "relevant": relevant,
        "source_level": "A",
        "discovery_only": 0,
        "topic_id": "dpu_inline",
    }


def test_appendix_requires_actual_deferred_deep_candidate():
    assert appendix_candidate_is_deferred(_candidate(status="DEFERRED_BUDGET"))
    assert not appendix_candidate_is_deferred(_candidate(status="RADAR", fulltext_required=0))
    assert not appendix_candidate_is_deferred(_candidate(status="RELEVANT", fulltext_required=1))


def test_related_only_candidate_cannot_be_relabelled_as_top4_tail():
    rows = {
        "https://example.com/deep-tail": _candidate(status="DEFERRED_BUDGET"),
        "https://example.com/related-only": _candidate(status="RADAR", fulltext_required=0),
    }

    class FakeDB:
        def fetchone(self, _sql, args):
            return rows.get(args[1])

    service = SimpleNamespace(db=FakeDB())
    appendix = {
        "dpu_inline": [
            {
                "title": "deep tail",
                "url": "https://example.com/deep-tail",
                "summary": "real deferred item",
            },
            {
                "title": "related only",
                "url": "https://example.com/related-only",
                "summary": "must not enter appendix",
            },
        ]
    }

    filtered = _filter_deferred_appendix(service, "run-1", appendix)

    assert [item["title"] for item in filtered["dpu_inline"]] == ["deep tail"]
    assert filtered["dpu_inline"][0]["selection_role"] == "DEFERRED_TOP4"


def test_reader_appendix_explains_contract_and_hides_internal_score():
    rendered = render_deferred_appendix_row(
        "DPU随路卸载",
        [
            {
                "title": "TurboRetry",
                "summary": "DPU卸载QUIC Retry。",
                "url": "https://example.com/turbo",
                "source_name": "arXiv",
                "published_at": "2026-08-03",
                "score": 95,
            }
        ],
    )

    assert "其他相关进展" in rendered
    assert "已达到深度候选门槛" in rendered
    assert "仅相关但未达到深度门槛" in rendered
    assert "95分" not in rendered
