from briefing_skill.reader_writing_contract import (
    issue_writing_contract_errors,
    item_writing_contract_errors,
    text_is_generic_boilerplate,
    title_conclusion_too_similar,
)


def test_item_title_must_not_repeat_core_conclusion():
    title = "Kairos将Prefill偏转到Decode节点以消除跨节点KV传输"
    item = {
        "title": title,
        "core_conclusion": title + "。",
        "mechanism": "按路径估算首Token时延后选择就地执行。",
        "result": "在目标负载下改善尾延迟。",
        "boundary": "仅在有限集群配置验证。",
        "project_relevance": "应验证网络状态参与路由的稳定收益。",
    }
    errors = item_writing_contract_errors(item)
    assert any("title and core_conclusion" in error for error in errors)


def test_title_conclusion_can_be_related_without_being_duplicate():
    assert not title_conclusion_too_similar(
        "Kairos：用Prefill偏转减少KV传输",
        "突发负载下它把部分预填充迁到空闲解码节点，在排队与传输之间动态选择更短路径。",
    )


def test_judgement_rejects_benchmark_dump():
    body = (
        "四个方案分别提升93.2%、7.63倍、81%和2.1倍，因此KV缓存正在成为分布式对象。"
        "对状态感知网络应继续验证。"
    )
    errors = issue_writing_contract_errors(
        {"judgements": [{"title": "KV缓存成为基础设施对象", "body": body}]}
    )
    assert any("numeric mentions" in error for error in errors)


def test_judgement_accepts_short_trend_meaning_implication():
    body = (
        "KV缓存正在从引擎内部状态变成跨节点可调度的系统对象。"
        "多类机制都把放置、迁移与重算决策向基础设施层下沉。"
        "状态感知网络应优先验证网络状态参与KV路由后能否稳定改善尾延迟。"
    )
    assert issue_writing_contract_errors(
        {"judgements": [{"title": "KV缓存走向基础设施级调度", "body": body}]}
    ) == []


def test_judgement_rejects_more_than_three_sentences():
    body = "趋势已经出现。机制正在下沉。边界仍需验证。项目应先做实验。"
    errors = issue_writing_contract_errors(
        {"judgements": [{"title": "基础设施边界变化", "body": body}]}
    )
    assert any("no more than 3 sentences" in error for error in errors)


def test_generic_appendix_reason_is_not_reader_copy():
    assert text_is_generic_boilerplate("与指定方向直接相关，并包含可验证机制。")
    assert not text_is_generic_boilerplate("Tiara把多轮远程依赖链压缩到单次往返。")
