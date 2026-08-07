from briefing_skill.topic_appendix_render import insert_inline_topic_appendices


def test_topic_appendix_is_inserted_before_next_topic():
    source = """
    <html><body><table>
      <tr><td><a id="topic-tpn"></a><b>TPN</b></td></tr>
      <tr><td>TPN deep item</td></tr>
      <tr><td><a id="topic-dpu_inline"></a><b>DPU</b></td></tr>
      <tr><td>DPU deep item</td></tr>
      <tr><td><span>热点雷达</span></td></tr>
    </table></body></html>
    """
    appendix = {
        "tpn": [
            {
                "title": "Additional KVCache paper",
                "summary": "提出新的传输机制，并给出原始来源。",
                "url": "https://arxiv.org/abs/2607.12345",
                "source_name": "arXiv",
                "published_at": "2026-07-20",
                "score": 72,
            }
        ]
    }
    rendered = insert_inline_topic_appendices(
        source,
        [{"id": "tpn", "name": "状态感知网络、TPN"}, {"id": "dpu_inline", "name": "DPU随路卸载"}],
        appendix,
    )
    assert "状态感知网络、TPN · 更多相关进展" in rendered
    assert "Additional KVCache paper" in rendered
    assert rendered.index("TPN deep item") < rendered.index("更多相关进展") < rendered.index("topic-dpu_inline")
    assert rendered.count("data-topic-appendix=\"1\"") == 1
