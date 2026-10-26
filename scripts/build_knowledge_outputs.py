#!/usr/bin/env python3
"""Assemble knowledge-materialization task outputs from a hand-written spec.

Bulk knowledge backfill helper: use it when several archived issues are
waiting for Roadmap/Idea materialization and writing every output JSON by
hand would be error-prone. The per-issue path after each send does not need
it; see docs/operations/knowledge-freshness.md.

Usage: python3 scripts/build_knowledge_outputs.py <spec.json>   (run from the repository root)
Spec fields:
  input, output         task input/output paths
  summary               new roadmap summary (stable topics)
  new_roadmap           optional {roadmap_id, branches: {branch_id: {name,
                        direction_ids}}}; creates a roadmap instead of
                        copying the previous one
  timeline              [{branch, item_id, reason}]
  timeline_updates      [{branch, item_id, reason}]; re-dates a recurring item
  ideas                 [{idea_id, evidence_for: [{item_id, reason}],
                          decision_reason}]
  direction_to_cluster  {direction_name: cluster_id} (frontier_exploration only)
Sanity checks: item must exist in published_evidence; timeline order per
branch must be non-decreasing by issue_date; more than 8 numeric mentions in
a reason or summary only prints a note. `knowledge apply` remains the only
validation gate.
"""
import copy
import hashlib
import json
import re
import sys


def numeric_mentions(text):
    return re.findall(r"\d+(?:\.\d+)?", text)


def main(spec_path):
    spec = json.load(open(spec_path))
    data = json.load(open(spec["input"]))
    issue = data["issue_date"]
    ev = {e["item_id"]: e for e in data["published_evidence"]}

    roadmap = None
    if data["topic"]["topic_id"] != "frontier_exploration":
        new_spec = spec.get("new_roadmap")
        if new_spec:
            roadmap = {
                "roadmap_id": new_spec["roadmap_id"],
                "topic_id": data["topic"]["topic_id"],
                "topic_name": data["topic"]["topic_name"],
                "evidence_scope": "published_archive_only",
                "updated_by_issue": issue,
                "summary": spec["summary"],
                "view_mode": "evidence_timeline",
                "branches": [
                    {
                        "branch_id": bid,
                        "name": meta["name"],
                        "direction_ids": meta["direction_ids"],
                        "status": "emerging",
                        "stages": [],
                        "evidence_timeline": [],
                        "open_questions": [],
                        "evidence_item_ids": [],
                        "source_urls": [],
                    }
                    for bid, meta in new_spec["branches"].items()
                ],
            }
        else:
            prev = data["previous_roadmap"]
            keep = ["roadmap_id", "topic_id", "topic_name", "evidence_scope",
                    "updated_by_issue", "summary", "view_mode", "branches"]
            roadmap = copy.deepcopy({k: prev[k] for k in keep})
            roadmap["updated_by_issue"] = issue
            roadmap["summary"] = spec["summary"]
        for add in spec.get("timeline", []):
            b = next(x for x in roadmap["branches"] if x["branch_id"] == add["branch"])
            item = ev[add["item_id"]]
            last = b["evidence_timeline"][-1]["issue_date"] if b["evidence_timeline"] else "0000-00-00"
            assert last <= issue, f"timeline order broken for {add['item_id']}"
            b["evidence_timeline"].append({
                "item_id": add["item_id"],
                "issue_date": issue,
                "source_urls": item["source_urls"],
                "reason": add["reason"],
            })
            b["evidence_item_ids"].append(add["item_id"])
            for u in item["source_urls"]:
                if u not in b["source_urls"]:
                    b["source_urls"].append(u)
            if len(numeric_mentions(add["reason"])) > 8:
                print(f"note: reason has many numerics: {add['reason'][:40]}...")

        for upd in spec.get("timeline_updates", []):
            b = next(x for x in roadmap["branches"] if x["branch_id"] == upd["branch"])
            entry = next(e for e in b["evidence_timeline"] if e["item_id"] == upd["item_id"])
            entry["issue_date"] = issue
            entry["reason"] = upd["reason"]
            print(f"re-dated {upd['item_id']} in {upd['branch']} to {issue}")

    if spec.get("summary") and len(numeric_mentions(spec["summary"])) > 8:
        print("note: summary has many numerics")

    ideas = []

    frontier = []
    if data["topic"]["topic_id"] == "frontier_exploration":
        mapping = spec["direction_to_cluster"]
        by_id = {c["cluster_id"]: c for c in data["previous_frontier_clusters"]}
        for cid in by_id:
            by_id[cid] = copy.deepcopy(by_id[cid])
        for item in data["published_evidence"]:
            if item["issue_date"] != issue:
                continue
            cid = mapping[item["direction_name"]]
            assert cid in by_id, f"unknown cluster {cid}"
            c = by_id[cid]
            assert item["item_id"] not in c["evidence_item_ids"], item["item_id"]
            c["evidence_item_ids"].append(item["item_id"])
            for u in item["source_urls"]:
                if u not in c["source_urls"]:
                    c["source_urls"].append(u)
            c["last_seen_issue"] = issue
        order = [c["cluster_id"] for c in data["previous_frontier_clusters"]]
        frontier = [by_id[cid] for cid in order]
    for upd in spec.get("ideas", []):
        src = next(i for i in data["previous_ideas"] if i["idea_id"] == upd["idea_id"])
        idea = copy.deepcopy(src)
        ids = []
        for row in upd["evidence_for"]:
            item = ev[row["item_id"]]
            idea["evidence_for"].append({
                "item_id": row["item_id"],
                "issue_date": issue,
                "source_urls": item["source_urls"],
                "reason": row["reason"],
            })
            ids.append(row["item_id"])
            if len(numeric_mentions(row["reason"])) > 8:
                print(f"note: idea reason has many numerics: {row['reason'][:40]}...")
        idea["last_updated_issue"] = issue
        idea["decision_log"].append({
            "event_id": "idea_decision_" + hashlib.sha1(
                f"{upd['idea_id']}|{issue}|evidence_added".encode()).hexdigest()[:19],
            "issue_date": issue,
            "decision": "evidence_added",
            "from_status": src["status"],
            "to_status": src["status"],
            "reason": upd["decision_reason"],
            "evidence_item_ids": ids,
        })
        ideas.append(idea)

    out = {"_task": data["_task"], "roadmap": roadmap, "ideas": ideas,
           "frontier_clusters": frontier}
    with open(spec["output"], "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("wrote", spec["output"])


if __name__ == "__main__":
    main(sys.argv[1])
