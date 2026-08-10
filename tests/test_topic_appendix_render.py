from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _render(topic_groups):
    root = Path(__file__).resolve().parents[1]
    env = Environment(
        loader=FileSystemLoader(root / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    return env.get_template("email.html").render(
        issue={"synthesis": {"headline": "headline"}, "date_to": "2026-08-10"},
        subject="briefing",
        footer="footer",
        topic_groups=topic_groups,
        judgement_refs=[],
        aihot_groups=[],
        aihot_count=0,
    )


def test_topic_appendix_is_rendered_inline_before_next_topic():
    groups = [
        {
            "id": "tpn",
            "name": "状态感知网络、TPN",
            "description": "",
            "items": [],
            "observations": [],
            "total_count": 1,
            "appendix": [
                {
                    "title": "Additional KVCache paper",
                    "summary": "提出新的传输机制，并给出原始来源。",
                    "url": "https://arxiv.org/abs/2607.12345",
                    "source_name": "arXiv",
                    "published_at": "2026-07-20",
                    "score": 72,
                    "links": [],
                    "family_size": 1,
                }
            ],
        },
        {
            "id": "dpu_inline",
            "name": "DPU随路卸载",
            "description": "",
            "items": [],
            "observations": [],
            "total_count": 0,
            "appendix": [],
        },
    ]

    rendered = _render(groups)

    assert "状态感知网络、TPN · 更多相关进展" in rendered
    assert "Additional KVCache paper" in rendered
    assert rendered.index('id="topic-tpn"') < rendered.index("更多相关进展") < rendered.index('id="topic-dpu_inline"')
    assert rendered.count('data-topic-appendix="1"') == 1


def test_structured_appendix_keeps_release_family_links_and_label():
    groups = [
        {
            "id": "tpn",
            "name": "状态感知网络、TPN",
            "description": "",
            "items": [],
            "observations": [],
            "total_count": 1,
            "appendix": [
                {
                    "title": "Project release family",
                    "summary": "两条更新合并速览。",
                    "url": "https://github.com/example/repo/releases/tag/v2",
                    "source_name": "GitHub",
                    "published_at": "2026-08-09",
                    "score": 80,
                    "family_size": 2,
                    "links": [
                        {"url": "https://github.com/example/repo/releases/tag/v2", "label": "v2"},
                        {"url": "https://github.com/example/repo/releases/tag/v1", "label": "v1"},
                    ],
                }
            ],
        }
    ]

    rendered = _render(groups)

    assert "2项合并" in rendered
    assert ">v2</a>" in rendered
    assert ">v1</a>" in rendered
