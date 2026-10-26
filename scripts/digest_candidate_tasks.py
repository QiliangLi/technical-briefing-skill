#!/usr/bin/env python3
"""Print a compact digest of Candidate discovery task inputs for one issue directory.

Bulk knowledge backfill helper: shows each task's type, trigger evidence and
the identity triples of previous candidates so duplicates are visible before
writing a spec. See docs/operations/knowledge-freshness.md.

Usage: python3 scripts/digest_candidate_tasks.py workspace/knowledge/candidate-tasks/<issue>
"""
import glob
import json
import os
import sys

d = sys.argv[1]
for p in sorted(glob.glob(os.path.join(d, "*.input.json"))):
    data = json.load(open(p))
    t = data["_task"]
    tid = os.path.basename(p).split(".")[0]
    ev = {e["item_id"]: e for e in data["published_evidence"]}
    print(f"===== {tid} type={t['type']} entity={t['entity_id']} issue={data['issue_date']}")
    prev = data.get("previous_candidates") or []
    if prev:
        for c in prev[-6:]:
            print("  PREV:", c["candidate_id"], c["disposition"], "|", c["identity"]["problem_key"], "+", c["identity"]["mechanism_key"], "+", c["identity"]["target_key"], "|", c["title"][:50])
    for iid in data["trigger_evidence_item_ids"]:
        e = ev.get(iid)
        if not e:
            print("  TRIGGER", iid, "(not in evidence)")
            continue
        print(f"  TRIG {iid} role={e.get('role')} {e.get('claim_strength','')}")
        print("     T:", e["title"])
        cc = (e.get("core_conclusion") or "")[:280].replace("\n", " ")
        print("     C:", cc)
    print()
