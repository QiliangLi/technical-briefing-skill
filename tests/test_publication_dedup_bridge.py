from briefing_skill.db import Database
from briefing_skill.publication_dedup_bridge import (
    exact_version_identity,
    project_exact_version_aliases,
)
from briefing_skill.publication_history import ensure_schema
from briefing_skill.utils import now_iso


def test_arxiv_abs_and_pdf_aliases_share_exact_version_identity():
    assert exact_version_identity("https://arxiv.org/abs/2608.05886v1") == "arxiv:2608.05886@v1"
    assert exact_version_identity("https://arxiv.org/pdf/2608.05886v1.pdf") == "arxiv:2608.05886@v1"
    assert exact_version_identity("https://arxiv.org/abs/2608.05886v2") == "arxiv:2608.05886@v2"


def test_published_v1_blocks_pdf_v1_alias_but_not_v2(tmp_path):
    db = Database(tmp_path / "workspace" / "briefing.sqlite")
    db.init()
    ensure_schema(db)
    stamp = now_iso()
    db.execute(
        """
        INSERT INTO published_sources(
          issue_id,identity_key,version_key,canonical_url,normalized_title,section,sent_at,message_id
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            "old-issue",
            "arxiv:2608.05886",
            "https://arxiv.org/abs/2608.05886v1",
            "https://arxiv.org/abs/2608.05886v1",
            "paper",
            "core",
            stamp,
            "msg",
        ),
    )
    db.create_run("new-run", "COLLECTED")
    for index, url in enumerate(
        [
            "https://arxiv.org/pdf/2608.05886v1.pdf",
            "https://arxiv.org/abs/2608.05886v2",
        ],
        1,
    ):
        db.execute(
            """
            INSERT INTO raw_items(
              id,run_id,source_id,discovery_source,source_level,discovery_only,title,
              original_url,canonical_url,identity_key,priority,payload_json,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                f"raw-{index}",
                "new-run",
                "arxiv",
                "arxiv",
                "A",
                0,
                f"paper-{index}",
                url,
                url,
                "arxiv:2608.05886",
                1,
                "{}",
                stamp,
            ),
        )

    assert project_exact_version_aliases(db, "new-run") == 1
    assert db.fetchone(
        "SELECT 1 AS ok FROM radar_history WHERE canonical_url=?",
        ("https://arxiv.org/pdf/2608.05886v1.pdf",),
    )["ok"] == 1
    assert db.fetchone(
        "SELECT 1 AS ok FROM radar_history WHERE canonical_url=?",
        ("https://arxiv.org/abs/2608.05886v2",),
    ) is None
