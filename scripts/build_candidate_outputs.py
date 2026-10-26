#!/usr/bin/env python3
"""Assemble idea-candidate-discovery task outputs from a hand-written spec.

Bulk knowledge backfill helper: use it when several archived issues are
waiting for Candidate discovery and writing every output JSON by hand would
be error-prone. The per-issue path after each send does not need it; see
docs/operations/knowledge-freshness.md.

Usage: python3 scripts/build_candidate_outputs.py <spec.json>   (run from the repository root)
Spec: {"tasks": [{"input": ..., "output": ..., "no_ops": {item_id:
[reason_code, reason]}, "candidates": [ {...} ], "candidate_updates": [...]}]}

Candidate specs carry identity/idea_type/title/problem/hypothesis/mechanism/
target/expected_effect/topic_ids/unknowns/validation_plan/disposition/
disposition_reason/evidence_item_ids/evidence_reasons/origin_kind/
origin_rationale. IDs, groups, urls, dates and the decision_log are derived.
`knowledge candidates apply` remains the only validation gate.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from briefing_skill.utils import source_identity_key, stable_hash  # noqa: E402


def build_candidate(spec, data):
    ev = {e["item_id"]: e for e in data["published_evidence"]}
    issue = data["issue_date"]
    keys = [spec["identity"][k] for k in ("problem_key", "mechanism_key", "target_key")]
    cid = "candidate_" + stable_hash(*keys, length=20)
    refs = []
    for item_id in spec["evidence_item_ids"]:
        item = ev[item_id]
        urls = list(item["source_urls"])
        refs.append({
            "item_id": item_id,
            "issue_date": item["issue_date"],
            "source_urls": urls,
            "reason": spec["evidence_reasons"][item_id],
            "independence_group": source_identity_key(urls[0]),
        })
    urls, groups = [], []
    for ref in refs:
        for u in ref["source_urls"]:
            if u not in urls:
                urls.append(u)
        if ref["independence_group"] not in groups:
            groups.append(ref["independence_group"])
    dates = [r["issue_date"] for r in refs]
    origin_kind = "single_evidence" if len(refs) == 1 else spec["origin_kind"]
    cand = {
        "schema_version": 1,
        "candidate_id": cid,
        "identity": spec["identity"],
        "idea_type": spec["idea_type"],
        "title": spec["title"],
        "problem": spec["problem"],
        "hypothesis": spec["hypothesis"],
        "mechanism": spec["mechanism"],
        "target": spec["target"],
        "expected_effect": spec["expected_effect"],
        "topic_ids": spec["topic_ids"],
        "origin": {
            "kind": origin_kind,
            "trigger_issue": max(dates),
            "rationale": spec["origin_rationale"],
        },
        "evidence": refs,
        "evidence_item_ids": list(spec["evidence_item_ids"]),
        "source_urls": urls,
        "independence_groups": groups,
        "unknowns": spec["unknowns"],
        "validation_plan": spec["validation_plan"],
        "disposition": spec["disposition"],
        "disposition_reason": spec["disposition_reason"],
        "related_candidate_ids": spec.get("related_candidate_ids", []),
        "related_idea_ids": spec.get("related_idea_ids", []),
        "first_seen_issue": min(dates),
        "last_updated_issue": max(dates),
        "decision_log": [{
            "event_id": "candidate_decision_" + hashlib.sha1(
                f"{cid}|{issue}|{spec['disposition']}".encode()).hexdigest()[:19],
            "issue_date": max(dates),
            "decision": spec["disposition"],
            "from_disposition": None,
            "to_disposition": spec["disposition"],
            "reason": spec["disposition_reason"],
            "evidence_item_ids": list(spec["evidence_item_ids"]),
            "actor": "agent",
        }],
    }
    return cand


def redate_candidate(prev, issue, reason):
    cand = dict(prev)
    cand["evidence"] = [dict(r, issue_date=issue) for r in prev["evidence"]]
    cand["first_seen_issue"] = issue
    cand["last_updated_issue"] = issue
    cand["origin"] = dict(prev["origin"], trigger_issue=issue)
    row = {
        "event_id": "candidate_decision_" + hashlib.sha1(
            f"{prev['candidate_id']}|{issue}|redate".encode()).hexdigest()[:19],
        "issue_date": issue,
        "decision": prev["disposition"],
        "from_disposition": prev["disposition"],
        "to_disposition": prev["disposition"],
        "reason": reason,
        "evidence_item_ids": list(prev["evidence_item_ids"]),
        "actor": "agent",
    }
    cand["decision_log"] = [*prev["decision_log"], row]
    return cand


def main(spec_path):
    spec = json.load(open(spec_path))
    for task in spec["tasks"]:
        data = json.load(open(task["input"]))
        issue = data["issue_date"]
        candidates = [build_candidate(c, data) for c in task.get("candidates", [])]
        prev_by_id = {c["candidate_id"]: c for c in data.get("previous_candidates", [])}
        for upd in task.get("candidate_updates", []):
            candidates.append(
                redate_candidate(prev_by_id[upd["candidate_id"]], issue, upd["reason"]))
        out = {
            "_task": data["_task"],
            "candidates": candidates,
            "no_ops": [
                {"item_id": item_id, "reason_code": reason[0], "reason": reason[1]}
                for item_id, reason in task.get("no_ops", {}).items()
            ],
            "covered_trigger_item_ids": data["trigger_evidence_item_ids"],
        }
        with open(task["output"], "w") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("wrote", task["output"])


if __name__ == "__main__":
    main(sys.argv[1])
