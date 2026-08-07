from __future__ import annotations

from briefing_skill.release_family import collapse_release_families
from briefing_skill.topic_appendix_render import _appendix_row


def test_same_github_project_appendix_updates_collapse_but_other_sources_do_not():
    appendix = {
        "tpn": [
            {
                "title": "LMCache v1 compatibility",
                "summary": "Adds connector compatibility for backend A.",
                "url": "https://github.com/LMCache/LMCache/releases/tag/v1",
                "source_name": "GitHub Release",
                "published_at": "2026-08-07",
                "score": 58,
                "project_key": "github:lmcache/lmcache",
            },
            {
                "title": "LMCache v2 dependency update",
                "summary": "Updates a transport dependency and fixes setup behavior.",
                "url": "https://github.com/LMCache/LMCache/releases/tag/v2",
                "source_name": "GitHub Release",
                "published_at": "2026-08-06",
                "score": 54,
                "project_key": "github:lmcache/lmcache",
            },
            {
                "title": "Independent KV transfer paper",
                "summary": "Proposes a different network mechanism.",
                "url": "https://arxiv.org/abs/2608.00001",
                "source_name": "arXiv",
                "published_at": "2026-08-05",
                "score": 71,
                "project_key": "arxiv:2608.00001",
            },
        ]
    }
    result = collapse_release_families(appendix)["tpn"]
    assert len(result) == 2
    family = result[0]
    assert family["family_size"] == 2
    assert "lmcache/lmcache" in family["title"]
    assert len(family["links"]) == 2
    assert result[1]["title"] == "Independent KV transfer paper"


def test_release_family_renderer_keeps_each_original_link():
    items = collapse_release_families(
        {
            "tpn": [
                {
                    "title": "Release A",
                    "summary": "Compatibility update A.",
                    "url": "https://github.com/example/repo/releases/tag/a",
                    "source_name": "GitHub Release",
                    "published_at": "2026-08-07",
                    "score": 55,
                    "project_key": "github:example/repo",
                },
                {
                    "title": "Release B",
                    "summary": "Compatibility update B.",
                    "url": "https://github.com/example/repo/releases/tag/b",
                    "source_name": "GitHub Release",
                    "published_at": "2026-08-06",
                    "score": 53,
                    "project_key": "github:example/repo",
                },
            ]
        }
    )["tpn"]
    rendered = _appendix_row("TPN", items)
    assert "2项合并" in rendered
    assert "releases/tag/a" in rendered
    assert "releases/tag/b" in rendered
