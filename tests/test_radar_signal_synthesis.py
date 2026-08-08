import json

from briefing_skill.radar_signal_synthesis import radar_semantic_errors


def _task():
    return {
        "task_type": "issue_synthesis",
        "metadata_json": json.dumps({"radar_signals_required": True}),
    }


def _input():
    return {
        "radar_candidates": [
            {
                "candidate_id": "a",
                "category": "存储与介质",
                "title": "HBF prototype",
                "summary": "A high-bandwidth flash prototype changes the bandwidth/capacity tradeoff for AI storage.",
                "url": "https://example.com/hbf",
            },
            {
                "candidate_id": "b",
                "category": "存储与介质",
                "title": "NAND controller",
                "summary": "A controller design reduces write amplification under a measured flash workload.",
                "url": "https://example.com/nand",
            },
            {
                "candidate_id": "c",
                "category": "AI Infra",
                "title": "Serving runtime",
                "summary": "A serving runtime changes request scheduling under bursty inference traffic.",
                "url": "https://example.com/runtime",
            },
            {
                "candidate_id": "d",
                "category": "Agent生态",
                "title": "Coding agent",
                "summary": "A coding agent reduces repository search calls using a persistent index.",
                "url": "https://example.com/agent",
            },
        ]
    }


def test_radar_signals_require_concrete_supported_sources():
    data = {
        "radar_signals": [
            {
                "category": "存储与介质",
                "signal": "高带宽闪存开始探索更靠近AI计算侧的数据层级",
                "summary": "候选信息显示关注点从单纯容量转向带宽与容量协同，值得继续观察其器件指标能否转化为系统端收益。",
                "source_urls": ["https://example.com/hbf", "https://example.com/nand"],
            }
        ]
    }
    assert radar_semantic_errors(_task(), _input(), data) == []


def test_radar_rejects_internal_selection_jargon_and_unknown_urls():
    data = {
        "radar_signals": [
            {
                "category": "AI Infra",
                "signal": "high-confidence A-level rule match",
                "summary": "这只是内部筛选原因，没有给技术读者提供任何具体的信息增量。",
                "source_urls": ["https://example.com/not-a-candidate"],
            }
        ]
    }
    errors = radar_semantic_errors(_task(), _input(), data)
    assert any("internal selection metadata" in error for error in errors)
    assert any("unknown source_urls" in error for error in errors)


def test_radar_does_not_reuse_one_source_for_multiple_signals():
    data = {
        "radar_signals": [
            {
                "category": "存储与介质",
                "signal": "信号一：HBF关注带宽容量协同",
                "summary": "第一条信号使用HBF候选来描述新的介质层级探索方向。",
                "source_urls": ["https://example.com/hbf"],
            },
            {
                "category": "存储与介质",
                "signal": "信号二：重复消费同一来源",
                "summary": "第二条信号不应再次使用同一个来源来制造额外的信息点。",
                "source_urls": ["https://example.com/hbf"],
            },
        ]
    }
    errors = radar_semantic_errors(_task(), _input(), data)
    assert any("reuses a source" in error for error in errors)
