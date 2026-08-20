from pathlib import Path

from bs4 import BeautifulSoup

from briefing_skill.reader_blocks_renderer_v2 import render_blocks_native


ROOT = Path(__file__).resolve().parents[1]


def test_native_renderer_replaces_legacy_placeholders_from_blocks() -> None:
    html = '''
    <html><body>
      <div style="display:none;max-height:0">旧预览</div>
      <td data-reader-role="deep-card">
        <td id="item-x">
          <div data-reader-meta="1">论文 · 2026-08-20</div>
          <h2>标题</h2>
          <p>陈旧 lead 文案。</p>
          <div data-reader-section-heading="1" data-reader-section-role="mechanism">旧标题</div>
          <p>陈旧 body 文案。</p>
          <div>阅读原文：<a href="https://example.com">来源</a></div>
        </td>
      </td>
    </body></html>
    '''
    readers = {
        "x": {
            "blocks": [
                {"heading_key": None, "text": "直接从 blocks 渲染的开场。"},
                {"heading_key": "result", "text": "这一段只讲关键结果。"},
            ]
        }
    }

    rendered = render_blocks_native(html, readers, issue_date="2026-08-20")
    soup = BeautifulSoup(rendered, "html.parser")
    node = soup.find(id="item-x")
    paragraphs = node.find_all("p", recursive=False)

    assert [p.get_text(strip=True) for p in paragraphs] == [
        "直接从 blocks 渲染的开场。",
        "这一段只讲关键结果。",
    ]
    assert all(p.get("data-reader-block") == "1" for p in paragraphs)
    assert "陈旧 lead 文案" not in rendered
    assert "陈旧 body 文案" not in rendered
    heading = node.select_one('[data-reader-section-heading="1"]')
    assert heading is not None
    assert heading.get_text(strip=True) == "关键结果"
    assert heading.get("data-reader-section-role") == "result"
    assert "阅读原文" in node.get_text(" ", strip=True)
    assert "AI语义Fabric技术情报（公测版） · 2026-08-20" in rendered


def test_archive_v2_renderer_uses_persisted_blocks_not_keyword_heading_inference() -> None:
    source = (ROOT / "briefing_skill/archive_editorial_layout.py").read_text(encoding="utf-8")

    assert "render_blocks_native" in source
    assert "decorate_reader_blocks" not in source


def test_bootstrap_installs_native_renderer_after_reader_v2() -> None:
    source = (ROOT / "briefing_skill/bootstrap.py").read_text(encoding="utf-8")

    assert "install_reader_blocks_renderer_v2()" in source
    assert source.index("install_reader_projection_v2()") < source.index(
        "install_reader_blocks_renderer_v2()"
    )
