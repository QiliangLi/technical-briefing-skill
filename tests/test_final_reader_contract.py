from __future__ import annotations

from types import SimpleNamespace

from briefing_skill.final_reader_contract import (
    filter_final_radar_groups,
    html_reader_contract_errors,
)


class FakeDB:
    def __init__(self):
        self.executed = []

    def execute(self, sql, args):
        self.executed.append((sql, args))


def test_final_radar_drops_signal_if_any_source_already_appears_in_deep_or_appendix():
    service = SimpleNamespace(
        db=FakeDB(),
        _topic_appendix_cache={
            "tpn": [{"url": "https://example.com/appendix", "links": []}]
        },
    )
    service._normalise_reference = lambda value: value.lower()
    issue = {
        "items": [
            {"sources": [{"url": "https://example.com/deep"}]}
        ]
    }
    groups = [
        {
            "name": "KVCache生态",
            "items": [
                {
                    "title": "duplicate-deep",
                    "summary": "depends on an already detailed source",
                    "url": "https://example.com/radar-a",
                    "sources": [
                        {"url": "https://example.com/radar-a"},
                        {"url": "https://example.com/deep"},
                    ],
                },
                {
                    "title": "duplicate-appendix",
                    "summary": "depends on appendix",
                    "url": "https://example.com/appendix",
                    "sources": [{"url": "https://example.com/appendix"}],
                },
                {
                    "title": "independent",
                    "summary": "new signal",
                    "url": "https://example.com/new",
                    "sources": [{"url": "https://example.com/new"}],
                },
            ],
        }
    ]

    filtered = filter_final_radar_groups(
        service, groups, issue_id=None, issue_data=issue
    )

    assert [item["title"] for item in filtered[0]["items"]] == ["independent"]


def test_html_rejects_deep_appendix_and_radar_source_overlap():
    html = """
    <table>
      <tr data-reader-row="deep-row"><td width="100%" data-reader-role="deep-card">
        <div data-reader-meta="1">论文 · 2026-08-09</div>
        <a href="https://example.com/a">Deep</a>
      </td></tr>
      <tr data-topic-appendix="1"><td><a href="https://example.com/a">Appendix</a></td></tr>
      <tr><td data-reader-role="radar-card"><a href="https://example.com/a">Radar</a></td></tr>
    </table>
    """

    errors = html_reader_contract_errors(html)

    assert any("Deep and topic appendix" in error for error in errors)
    assert any("Radar repeats a source already used by a detailed item" in error for error in errors)
    assert any("Radar repeats a source already used by a topic appendix" in error for error in errors)


def test_html_requires_orphan_deep_card_to_be_full_width_and_hides_scores():
    html = """
    <table>
      <tr data-reader-row="deep-row"><td width="50%" data-reader-role="deep-card">
        <div data-reader-meta="1">论文 · 2026-08-09 · 95分</div>
        <a href="https://example.com/a">Deep</a>
      </td></tr>
    </table>
    """

    errors = html_reader_contract_errors(html)

    assert any("100% width" in error for error in errors)
    assert any("internal selection scores" in error for error in errors)


def test_clean_final_html_passes_layout_score_and_url_contracts():
    html = """
    <table>
      <tr data-reader-row="deep-row"><td width="100%" data-reader-role="deep-card">
        <div data-reader-meta="1">论文 · 2026-08-09</div>
        <a href="https://example.com/deep">Deep</a>
      </td></tr>
      <tr data-topic-appendix="1"><td><a href="https://example.com/appendix">Appendix</a></td></tr>
      <tr><td data-reader-role="radar-card"><a href="https://example.com/radar">Radar</a></td></tr>
    </table>
    """

    assert html_reader_contract_errors(html) == []
