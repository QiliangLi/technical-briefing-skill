from briefing_skill.reader_quality_guard_v2 import (
    issue_synthesis_readability_errors,
    reader_projection_quality_errors,
)


def _result(title: str, text: str = "这是一段正常长度的技术说明。") -> dict:
    return {
        "title": title,
        "blocks": [{"heading_key": None, "text": text}],
    }


def test_issue_wide_project_verb_title_rhythm_is_rejected() -> None:
    data = {
        "results": [
            _result("Alpha让缓存调度更稳定"),
            _result("Beta把索引更新移到后台"),
            _result("Gamma用预取减少等待时间"),
            _result("Delta通过批处理降低开销"),
            _result("为什么这里不需要更多副本"),
        ]
    }

    errors = reader_projection_quality_errors(data)

    assert any("title rhythm is too uniform" in error for error in errors)


def test_mixed_title_rhythm_is_not_forced_into_a_rotation() -> None:
    data = {
        "results": [
            _result("Alpha让缓存调度更稳定"),
            _result("Beta把索引更新移到后台"),
            _result("固定批次并不是确定性的必要条件"),
            _result("跨域预取什么时候才值得做"),
            _result("少一层网络反而降低尾延迟"),
        ]
    }

    errors = reader_projection_quality_errors(data)

    assert not any("title rhythm is too uniform" in error for error in errors)


def test_reader_card_has_a_total_length_fuse() -> None:
    data = {
        "results": [
            {
                "title": "一个过长的卡片",
                "blocks": [
                    {"heading_key": None, "text": "甲" * 250},
                    {"heading_key": "mechanism", "text": "乙" * 250},
                    {"heading_key": "result", "text": "丙" * 250},
                ],
            }
        ]
    }

    errors = reader_projection_quality_errors(data)

    assert any("block text must total <=720" in error for error in errors)


def test_issue_judgement_limits_are_broad_but_not_unbounded() -> None:
    data = {
        "judgements": [
            {
                "title": "判断" * 25,
                "body": "第一句包含1个指标。第二句包含2个指标。第三句包含3个指标。第四句包含4个指标。第五句包含5个指标。" + "补" * 260,
            }
        ]
    }

    errors = issue_synthesis_readability_errors(data)

    assert any("title must be <=48" in error for error in errors)
    assert any("body must be <=300" in error for error in errors)
    assert any("no more than 4 sentences" in error for error in errors)
    assert any("at most 4 numeric mentions" in error for error in errors)
