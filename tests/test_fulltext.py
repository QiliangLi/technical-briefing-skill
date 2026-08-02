from briefing_skill.fulltext import FulltextService


def test_sanitize_text_replaces_lone_surrogates() -> None:
    dirty = "valid\ud800text\udfff"

    cleaned = FulltextService._sanitize_text(dirty)

    assert cleaned == "valid?text?"
    assert cleaned.encode("utf-8")
