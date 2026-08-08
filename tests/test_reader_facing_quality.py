from briefing_skill.reader_facing_quality import _contains_internal_reason


def test_internal_selection_reason_is_not_reader_content():
    assert _contains_internal_reason("high-confidence A-level rule match")
    assert _contains_internal_reason("selection reason: strong lexical match")
    assert not _contains_internal_reason("提出基于KV位置与链路负载的联合调度，减少跨节点KV搬移。")
