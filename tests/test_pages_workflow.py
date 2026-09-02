from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pages_workflow_publishes_knowledge_store() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
        encoding="utf-8"
    )

    assert "- 'knowledge/**'" in workflow
    assert 'cp -R knowledge "$publish_dir/knowledge"' in workflow


def test_pages_workflow_gates_publication_on_a_fresh_derived_graph() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
        encoding="utf-8"
    )

    # The authoritative store must pass its own validation, then the graph is
    # rebuilt deterministically and validated against the current archive/
    # knowledge inputs before the site is assembled; a stale or broken graph
    # must stop publication instead of shipping it.
    gate = workflow.find("Rebuild and validate the derived knowledge graph")
    assemble = workflow.find("Assemble static site")
    assert gate != -1 and assemble != -1 and gate < assemble
    assert "knowledge validate" in workflow
    assert "knowledge graph build" in workflow
    assert "knowledge graph validate" in workflow
    # Freshness gate: the manifest is rebuilt after the graph and validated;
    # a manifest claiming knowledge_complete while watermarks lag must fail
    # publication instead of shipping stale summaries as current change.
    manifest_build = workflow.find("knowledge manifest build")
    manifest_validate = workflow.find("knowledge manifest validate")
    graph_validate = workflow.find("knowledge graph validate")
    assert manifest_build != -1 and manifest_validate != -1
    assert graph_validate != -1 and graph_validate < manifest_build < manifest_validate < assemble
    assert "python3 -m pip install --quiet -e ." in workflow
    # The gate rewrites knowledge/graph.json inside the runner checkout; the
    # publish step must restore it so the orphan-branch switch stays clean.
    publish = workflow.find("Publish gh-pages branch")
    restore = workflow.find("git checkout -- knowledge/graph.json")
    assert publish != -1 and restore != -1 and publish < restore


def test_pages_workflow_triggers_on_graph_builder_and_schema_changes() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
        encoding="utf-8"
    )

    # A builder, schema, or dependency change must redeploy the site; otherwise
    # gh-pages would keep serving a graph built by the previous code.
    for path in (
        "briefing_skill/knowledge_graph.py",
        "briefing_skill/knowledge_materialization.py",
        "schemas/**",
        "briefing.py",
        "pyproject.toml",
        "requirements.txt",
    ):
        assert f"- '{path}'" in workflow, path
