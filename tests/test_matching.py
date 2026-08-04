import json
from pathlib import Path

from briefing_skill.config import ConfigBundle
from briefing_skill.db import Database
from briefing_skill.matching import RuleMatcher
from briefing_skill.paths import Paths
from briefing_skill.utils import now_iso


def test_explicit_hint_creates_single_candidate(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = ConfigBundle.load(Paths(root))
    db = Database(tmp_path / "briefing.sqlite")
    db.init()
    db.create_run("r1")
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO raw_items(id,run_id,source_id,discovery_source,source_level,discovery_only,title,summary,original_url,aihot_url,canonical_url,published_at,discovered_at,authors_json,external_id,topic_hint,direction_hint,priority,content_hash,payload_json,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("x","r1","fixture","fixture","A",0,"CodeGraph accelerates coding agents","repository graph reduces read and grep","https://x","","https://x",now_iso(),now_iso(),"[]","","agent_acceleration","code_graph",20,"h",json.dumps({}),now_iso()),
        )
    candidates = RuleMatcher(config, db).create_candidates("r1")
    assert len(candidates) == 1
    assert candidates[0]["direction_id"] == "code_graph"
