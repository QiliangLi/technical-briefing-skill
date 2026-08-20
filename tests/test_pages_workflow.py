from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pages_workflow_publishes_knowledge_store() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
        encoding="utf-8"
    )

    assert "- 'knowledge/**'" in workflow
    assert 'cp -R knowledge "$publish_dir/knowledge"' in workflow
