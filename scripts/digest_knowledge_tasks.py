#!/usr/bin/env python3
"""Print a compact digest of knowledge task inputs for one issue directory.

Bulk knowledge backfill helper: it lets the Agent read a whole issue's
knowledge tasks (previous roadmap/ideas/clusters plus this issue's new
evidence) without loading every input JSON into context. See
docs/operations/knowledge-freshness.md.

Usage: python3 scripts/digest_knowledge_tasks.py workspace/knowledge/tasks/<issue> [item_id ...]
Extra item_ids mark recurring items whose timeline entry must be re-dated.
"""
import glob
import json
import os
import sys

d = sys.argv[1]
redates = sys.argv[2:]  # item_ids whose recurrence needs re-dating
for p in sorted(glob.glob(os.path.join(d, "*.input.json"))):
    data = json.load(open(p))
    t = data["topic"]
    issue = data["issue_date"]
    print(f"===== {os.path.basename(p).split('.')[0]} topic={t['topic_id']} ({t['topic_name']}) issue={issue}")
    if t["topic_id"] != "frontier_exploration":
        prev = data.get("previous_roadmap")
        if prev:
            print("PREV branches:", [(b["branch_id"], b["name"]) for b in prev["branches"]])
            print("PREV view_mode:", prev["view_mode"], "| updated_by:", prev["updated_by_issue"])
            print("PREV summary:", prev["summary"][:300])
        else:
            print("NO previous roadmap (new)")
        pis = data.get("previous_ideas") or []
        print("PREV ideas:", [(i["idea_id"], i["status"]) for i in pis][:12])
    else:
        pfc = data.get("previous_frontier_clusters") or []
        print("PREV clusters:", [(c["cluster_id"], c["last_seen_issue"]) for c in pfc])
    recurred = [r for r in redates if r in data["current_issue_evidence_item_ids"]]
    if recurred:
        print("!! RECURRING items needing re-date:", recurred)
    for e in data["published_evidence"]:
        if e["issue_date"] != issue:
            continue
        print(f"NEW {e['item_id']} [{e.get('direction_id')}/{e.get('direction_name')}] role={e.get('role')} {e.get('claim_strength','')}")
        print("   T:", e["title"])
        cc = e.get("core_conclusion") or ""
        print("   C:", cc[:600].replace("\n", " "))
        for k in ("mechanism", "result", "boundary", "project_relevance"):
            v = (e.get(k) or "").strip()
            if v:
                print(f"   {k[0].upper()}: {v[:400]}".replace("\n", " "))
    print()
