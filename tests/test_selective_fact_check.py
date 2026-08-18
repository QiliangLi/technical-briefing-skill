from pathlib import Path

from briefing_skill.evidence_gate import evidence_gate


def _item(**overrides):
    item = {
        "title": "KV缓存管理更新",
        "core_conclusion": "系统把缓存状态纳入调度决策。",
        "mechanism": "调度器读取缓存位置后选择节点。",
        "result": "实验显示请求时延下降。",
        "boundary": "结果仅覆盖论文中的测试集群。",
        "project_relevance": "可以验证状态感知调度是否适合现有系统。",
        "sources": [
            {
                "publisher": "paper",
                "url": "https://example.org/paper",
                "source_level": "A",
                "primary": True,
            }
        ],
    }
    item.update(overrides)
    return item


def test_low_risk_single_primary_source_skips_llm_review() -> None:
    decision = evidence_gate(_item(), [{"mechanism": "缓存位置参与调度", "result": "时延下降"}])
    assert decision["decision"] == "PASS"
    assert decision["reasons"] == []


def test_grounded_numbers_do_not_trigger_review_by_themselves() -> None:
    item = _item(result="在测试集群中，P99时延下降20%。")
    decision = evidence_gate(item, [{"result": "P99 latency was reduced by 20% in the evaluated cluster."}])
    assert decision["decision"] == "PASS"
    assert decision["numbers_checked"] == ["20"]


def test_ungrounded_number_strong_claim_and_non_a_source_trigger_review() -> None:
    item = _item(
        result="生产环境吞吐最高提升37%。",
        sources=[
            {
                "publisher": "blog",
                "url": "https://example.org/blog",
                "source_level": "B",
                "primary": True,
            }
        ],
    )
    decision = evidence_gate(item, [{"result": "prototype throughput improved"}])
    assert decision["decision"] == "REVIEW"
    assert "number_not_grounded:37" in decision["reasons"]
    assert "strong_comparative_or_superlative_claim" in decision["reasons"]
    assert "non_a_level_source" in decision["reasons"]


def test_multi_source_synthesis_triggers_review() -> None:
    decision = evidence_gate(_item(), [{"claim": "a"}, {"claim": "b"}])
    assert decision["decision"] == "REVIEW"
    assert "multi_source_synthesis" in decision["reasons"]


def test_selective_gate_is_installed_after_reader_projection() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "briefing_skill" / "bootstrap.py").read_text(encoding="utf-8")
    assert source.index("install_reader_projection()") < source.index("install_selective_fact_check()")
