# Replay Comparison — PR20–PR24 on frozen input

- **Old run:** `2026-08-08-200543` (code at `0b8e24d`, **pre** PR20–24)
- **Replay run:** `2026-08-08-200543-replay-pr20-24` (current `main`, incl. PR20–24)
- **Method:** forked the old run's 616 collected `raw_items` into a new run with **no re-collection and no fulltext re-download** (offline guard `BRIEFING_OFFLINE_REPLAY=1`; raw fulltext reused from the global cache). Input data is fixed; only the processing code changed.
- PR map: PR20 `c2ae0e5` enforce Technology Value before deep selection · PR21 `c36ecde` balanced evidence + repair health · PR22 `2dfc29c` unify judgement/clean reader output · PR23 `d8870d8` storage-media deep topic · PR24 `f785fc2` signal-centric radar.

## 1. Overall run statistics

| Metric | Old Run | Replay | Change |
|---|---:|---:|---:|
| Raw candidates (raw_items) | 616 | 616 | 0 (frozen input) |
| Routed candidates | 589 | 589 | 0 |
| Relevance agent tasks | 22 | 6 | −16 (relevance cache reused) |
| Deep fact candidates (fact_extraction) | 16 | 18 | +2 |
| Evidence Repair | 13 | 5 | **−8** |
| **Repair Rate** | **81.25%** | **27.78%** | **−53.5 pp** |
| First-pass fact success | 18.8% | 72.2% | +53.4 pp |
| Item Writing batches | 4 | 4 | 0 |
| Fact Check batches | 4 | 4 | 0 |
| Issue Synthesis | 1 | 1 | 0 |
| Total agent tasks | 60 | 38 | −22 |
| Final deep items | 16 | 16 | 0 |
| Agent read char proxy | 1,815,182 | 972,451 | −46% |
| Fact-check pass | 16/16 (100%) | 16/16 (100%) | — |
| Numeric condition coverage | 100% | 100% | — |
| Primary-source resolve | 100% | 88.9% | −11.1 pp |
| `DEFERRED_FETCH` (offline cache miss) | 0 | 60 | n/a (replay-only) |

> Relevance tasks dropped 22→6 because the global relevance cache legitimately restored the old judgments (same source fingerprints + evaluator version); PR20 selection then re-ran on top. The agent-read proxy fell ~46% for the same reason.

## 2. TPN Deep Selection — before/after

**Old (pre-PR20) TPN deep** — all 4 taken via the deterministic “high-confidence” accept path: `relevance_score == rule_score` and `technology_value = None` (never assessed):

| # | Title | rel | rule | tech_value | path |
|---|---|---:|---:|---:|---|
| 1 | vllm-project/vllm v0.25.0 (**release**) | 130 | 130 | **None** | deterministic accept |
| 2 | ExpertPlex | 113.6 | 113.6 | **None** | deterministic accept |
| 3 | AAFLOW+ | 105.6 | 105.6 | **None** | deterministic accept |
| 4 | Alibaba Cloud WAIC (**product launch**) | 103.6 | 103.6 | **None** | deterministic accept |

Meanwhile genuinely high-tech papers were **DEFERRED**: TensorCast (tech 19), Tiara (19), Topology-Aware Data Movement (17), HBM-Is-Not-All (16), An-Internet-for-KV (16).

**Replay (PR20) TPN** — deterministic accept path removed; every deep candidate is agent-judged and ranked by `technology_selection_score = relevance·0.8 + tech_value`:

| # | Title | rel | rule | tech_value | tech_sel_score | outcome |
|---|---|---:|---:|---:|---:|---|
| 1 | AAFLOW+ | 93 | 105.6 | 19 | 93.2 | **selected (deep)** |
| 2 | An Internet for the KV Cache | 66 | 95.6 | 14 | 66.8 | **selected (deep)** |
| — | vllm v0.25.0 | 22 | 130 | 6 | — | **REJECTED** (was deep @ rel 130) |
| — | Alibaba WAIC | 66 | 103.6 | 14 | — | RADAR (was deep) |
| — | ExpertPlex | 65 | 113.6 | 14 | — | RADAR (was deep) |

**Verdict: PR20 fixes the reported defect.** The high-rule-match release `vllm v0.25.0` moved from a deep slot (rel 130, tech never assessed) to **REJECTED (rel 22, tech 6)** after a real relevance+Technology-Value pass. The product launch (Alibaba WAIC) and ExpertPlex dropped to Radar. The deep slots now go to tech-assessed candidates (AAFLOW+ tech 19). **Caveat:** the even-higher-tech papers (TensorCast/Tiara tech 19) are ranked deep-worthy by PR20 but hit `DEFERRED_FETCH` — their fulltext is not in the offline cache (they were never fetched in the old run), so they could not complete fact extraction in this replay. This is an input/cache limitation of offline replay, **not** a PR20 defect.

## 3. Deferred / Appendix high-value audit

PR20 selected several TPN candidates as deep-worthy (tech_value ≥ 14) that did not all become final deep items. Two reasons are visible, both **explicit policy, not invariant violations**:

- **Offline cache (`DEFERRED_FETCH`, 60 candidates):** high-tech papers (TensorCast tech 19, Tiara tech 19, Topology-Aware 16, HBM-Not-All 16, SmartGen 15) were selected for deep but had no cached fulltext → deferred under the offline rule. Override reason = `fetch_status=FALLBACK` / `DEFERRED_FETCH` (deterministic, recorded).
- **Budget/diversity caps** (`max_fact_candidates_total=16`, 4/topic, 2/direction, 1/project): e.g. An-Internet-for-KV (tech 16) ended `DEFERRED_BUDGET` once the TPN topic cap was filled.

No candidate was deferred **without** a recorded, policy-grounded reason → **no selection-invariant violation** detected. (The one ambiguity — that the *highest*-tech TPN papers couldn’t be deep only because of the offline cache — is a replay artifact, surfaced honestly rather than hidden.)

## 4. Evidence Repair comparison

Old run `front-evidence-v2` front-loaded Abstract/Intro, so Evaluation/Results were missed → 13/16 gaps → 81.25% repair (status `warning`).

Replay `balanced-evidence-v2` splits the pack across context/mechanism/results/boundary → first-pass success 72.2%.

| Old repair (13/16) | Replay repair (5/18) |
|---|---|
| repair was the **default** path | repair is the **exception** path |
| 81.25% rate (`warning`) | 27.78% rate (just over 0.25 gate, still `warning`) |

Replay repair items (5): CodeGrep, GPU-sparse-inference, ReMP, AAFLOW+ (+1 from the refill batch). Each is a **precision gap** (a specific missing number, e.g. the exact baseline behind a headline speedup), not a section-coverage failure. Two resolved fully on repair (ReMP → quality 65→85; AAFLOW+ → 65→78); three retained conservative limits. **Repair amplification is dramatically reduced**, though the rate sits marginally above the strict 0.25 “healthy” threshold, so it is not yet fully green.

## 5. Storage-media topic verification

`storage_media` is now a registered deep topic (9 deep topics total; `topics-media.yaml` + `config/project-context/storage-media.md` loaded). However, **the frozen input contains no genuine storage-media candidates**: the 25 raw_items matching storage terms (NAND/Flash/SSD/HBF/…) are all false positives (KV-cache, CXL-memory, attention, GPU papers) — none is a real NAND/HBF/HAMR/NVM device paper. This is because the input was collected under pre-PR23 code, which had no storage-media collection queries.

- candidates routed to `storage_media`: **0**
- → relevance / deep / appendix for storage_media: **0**

**Conclusion:** storage_media is correctly wired into competition, but this offline replay cannot exercise it — there is nothing in the frozen input to route. (This is an expected property of replaying a pre-storage-media collection; it should be re-validated on a fresh collection that includes storage queries. We did **not** fabricate a storage deep item.)

## 6. Reader-facing regression

| Check | Required | Replay result |
|---|---|---|
| Standalone “项目影响” section removed | NO | ✅ absent; substance folded into 本期判断 |
| Project impact folded into 本期判断 | YES | ✅ (validator pass “Project impact is merged into 本期判断”) |
| Internal selection-metadata leak (`high-confidence`, `A-level rule match`, `rule_score`, …) | 0 | ✅ 0 (validator pass “Reader output contains no internal selection metadata”) |
| Deep items show original paper/source title (`论文/来源：…`) | YES | ✅ injected post-render via `data-source-title` |
| Appendix entries are real signals | YES | ✅ |
| Validator catches these | YES | ✅ (reader_facing_quality checks active) |

Internal `project_insights` (4) still exist in `synthesis.json` for traceability, but are not rendered as a separate section — consistent with PR22.

## 7. Radar comparison

Old radar: article-centric (title + 1-line summary, sourced from rule-matched candidates), and **leaked the internal discovery brand “AI HOT”** into the email.

Replay radar (PR24): **signal-centric**, 6 signals synthesized from lightweight candidate metadata (no new fulltext/facts/writer/factcheck; reuses `issue_synthesis`):

1. `[Agent生态]` HarnessOpt-Bench — benchmark for harness-optimization under a fixed eval budget.
2. `[KVCache生态]` LMCache 0.5.3 GA + ROCm (MI300X/MI325X/MI350X/MI355X) — KV-transfer stack maturing cross-vendor.
3. `[AI Infra]` Carbon-aware real-time inference routing to the cleanest grid.
4. `[AI Infra]` CommBench — benchmark for LLM-authored GPU collective-communication code.
5. `[其他技术前沿]` Survey of chiplet-era hardware design & security.
6. `[存储与介质]` Salami Attack — stealthy collusive memory-poisoning of agent long-term memory.

Assessment: 1–4 are **genuine technical signals** (a release, two benchmarks, a routing idea). 5 is a survey (lower density but real). 6 is a real security signal but arguably mis-categorized (agent memory, not storage media). No signal is a bare title rewrite; no internal rule-match language; no source duplicated across signals. The radar is a meaningful improvement over the old article dump. (Density could be higher — only 6 signals, by design “prefer few high-density signals”.)

---

## Answers to the 7 required questions

1. **TPN Deep Selection improved?** ✅ Yes. The deterministic accept path is gone; `vllm v0.25.0` (release, was deep @ rel 130/tech None) → REJECTED (rel 22/tech 6). Deep slots now go to tech-assessed AAFLOW+ (tech 19) and Internet-for-KV. The highest-tech papers (TensorCast/Tiara) are ranked deep-worthy but blocked only by the offline cache, not by selection.
2. **Repair rate from 81.25% → ?** **27.78%** (13/16 → 5/18). First-pass success 18.8% → 72.2%. Still marginally above the 0.25 “healthy” gate (status `warning`).
3. **Internal selection-metadata leakage?** ✅ **0** (validator confirms).
4. **Standalone “项目影响” removed and merged into 本期判断?** ✅ Yes; substance folded into judgements, not merely deleted.
5. **Deep items show original paper/source title?** ✅ Yes (`论文/来源：…` via `data-source-title`).
6. **Storage-media in formal deep competition?** ⚠️ Registered and wired, but **0 candidates** in this frozen input (collected pre-PR23) — could not be exercised. No fabricated deep item.
7. **Radar from article dump → real signals?** ✅ Yes — 6 signal-centric entries (signal / what-changed / why / source_urls), no internal language, no dup sources.

## Bugs found & fixed during replay (minimal, tested)

1. **No offline/fulltext-no-re-fetch mode existed.** Added an env-gated guard at `FulltextService._fetch` (`BRIEFING_OFFLINE_REPLAY=1`): on a cache miss it raises instead of calling `http.get`; the candidate degrades to `FALLBACK`→`DEFERRED_FETCH` with no fact task. Cache hits proceed normally. Regression test: `tests/test_offline_replay_guard.py`.
2. **PR24 radar signal `source_name` leaked internal discovery brands.** `_signal_groups` set `source_name = discovery_source or …`, surfacing “AI HOT” in the reader-facing radar. Fixed to use the original-source hostname (arXiv/GitHub/domain), since radar links to the original source. Regression test: `tests/test_radar_signal_source_name.py`. (Note: the appendix path `coverage_policy._topic_appendix` has the same `discovery_source`-fallback pattern and was patched post-hoc in the original run; a permanent fix there is the one remaining cleanup.)

All 173 pre-existing tests still pass after both edits.

## Remaining issues / caveats

- **Offline cache limits the deep set.** 60 candidates were `DEFERRED_FETCH` (no cached fulltext), so PR20’s preferred high-tech TPN papers (TensorCast/Tiara) couldn’t be fact-extracted. The TPN before/after is therefore *directionally* conclusive but understates PR20’s full effect; re-validate on a fresh online collection for the complete picture.
- **Repair rate 27.78%** is a large improvement but still just above the 0.25 `healthy` gate.
- **Primary-source resolve 88.9%** (vs 100%): 2 of 18 replay deep sources unresolved — worth a quick check on a future run.
- **`coverage_policy._topic_appendix` discovery-source fallback** is the twin of the radar bug fixed above; not yet permanently patched (low risk; validator catches any leak).
- **storage_media** needs a fresh collection with storage queries to truly validate (out of scope for an offline replay).

## Artifacts

- Replay run: `workspace/runs/2026-08-08-200543-replay-pr20-24/`
- Briefing email: `workspace/runs/2026-08-08-200543-replay-pr20-24/email.html`
- Review HTML: `workspace/runs/2026-08-08-200543-replay-pr20-24/review.html`
- Synthesis (judgements + project_insights + radar_signals): `workspace/runs/2026-08-08-200543-replay-pr20-24/issue/synthesis.json`
- Validation: `workspace/runs/2026-08-08-200543-replay-pr20-24/validation.json` — **0 failures, 0 warnings, 13 passes**
- This report: `workspace/runs/2026-08-08-200543-replay-pr20-24/replay-comparison.md`
- (No PDF step exists in this pipeline.)
