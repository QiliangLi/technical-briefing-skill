from briefing_skill.editorial_batch import _id_set_errors, _pack_batches


def _entry(name: str, size: int, priority: float = 0):
    return {
        "payload": {"event_id": name, "text": "x" * size},
        "priority": priority,
    }


def test_editorial_batch_packing_respects_item_and_character_limits():
    entries = [_entry("a", 100), _entry("b", 100), _entry("c", 100), _entry("d", 100), _entry("e", 100)]
    batches = _pack_batches(entries, max_items=4, max_chars=10000)
    assert [[row["payload"]["event_id"] for row in batch] for batch in batches] == [
        ["a", "b", "c", "d"],
        ["e"],
    ]

    char_limited = _pack_batches(entries[:3], max_items=4, max_chars=260)
    assert len(char_limited) >= 2
    assert [row["payload"]["event_id"] for batch in char_limited for row in batch] == ["a", "b", "c"]


def test_batch_result_ids_must_match_exact_input_set():
    assert _id_set_errors(["a", "b"], ["a", "b"], "batch") == []
    errors = _id_set_errors(["a", "b"], ["a", "a", "x"], "batch")
    assert any("duplicate" in error for error in errors)
    assert any("omits" in error for error in errors)
    assert any("unknown" in error for error in errors)
    assert any("exactly one" in error for error in errors)
