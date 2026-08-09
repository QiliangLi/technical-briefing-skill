# Three-Run Comparison — Original · PR20–24 Replay · PR25+Media Replay

Three independent runs, frozen-input preserved across all three (the original 616
collected raw_items are byte-identical; run C adds 3 storage-media items). Code base
differs: **A** at `0b8e24d` (pre-PR20), **B** at `847d021` (PR20–24), **C** at `1c91f36`
(PR25 topic-local Top4 + PR26 token telemetry + this run's storage-media supplement).

- A = `2026-08-08-200543` (original E2E)
- B = `2026-08-08-200543-replay-pr20-24`
- C = `2026-08-08-200543-replay-pr25-media` (this run)

> **Method for C (token honesty + cache reuse):** C forked A's frozen 616 raw_items
> (`rp2-` ids, no re-collection) and reused content-keyed caches (relevance /
> Technology-Value / raw-fulltext / fact). For the 616, relevance/Technology-Value and
> item/fact-check judgments that are *identical content* to B were reused deterministically
> (B already Agent-judged them); only **net-new** Agent work ran — the storage-media
> supplement, the PR25-newly-deep 616 papers whose facts were not previously extracted,
> and a fresh issue synthesis. No product code was modified. See `media-search-audit.md`.

---

## 1. Overall structure

| Metric | A: Original | B: PR20–24 | C: PR25+Media |
|---|---:|---:|---:|
| Raw items | 616 | 616 | **619** (+3 media) |
| Routed candidates | 589 | 589 | 593 |
| Relevance agent tasks | 22 | 6 | 7 (cache + deterministic reuse) |
| Fact-extracted (deep) | 16 | 18 | **23** |
| `DEFERRED_FETCH` (offline miss) | 0 | 60 | 40 |
| Evidence-Repair tasks | 13 (81.25%) | 5 (27.78%) | 4 (3 skipped¹) |
| Brief items (PASS) | 16 / 16 | 16 / 16 | **23 / 23** |
| Issue items (rendered) | 14 | 16 | 23 |
| Appendix entries | 39 | 39 | 38 |
| Radar signals | 8 | 6 | 5 |
| Validation | 0 fail / 0 warn / 11 pass | 0 / 0 / 11 | **0 / 0 / 13** |

¹ C skipped 3 minor-precision repairs on already-good (q84) facts to bound token cost;
the `evidence_gaps` are retained (honest), not hidden. Repair rate is therefore not
directly comparable across C.

## 2. Per-topic Deep (fact-extracted) counts

| Topic | A: Original | B: PR20–24 | C: PR25+Media | Change C vs B |
|---|---:|---:|---:|---|
| tpn | 4 | 3 | **4** | +1 (Top4 restored) |
| agent_acceleration | 4 | 3 | **4** | +1 (Top4 restored) |
| ai_chip_accelerator | 1 | 4 | 4 | — |
| cross_region | 3 | 4 | 4 | — |
| memory_dsa | 1 | 2 | 2 | — |
| ai_infra_horizontal | 2 | 2 | 2 | — |
| dpu_inline | 1 | 0 | 0 | — |
| optical_network | 0 | 0 | 0 | — |
| **storage_media** | **0** | **0** | **3** | **+3 (NEW topic formed)** |
| **Total deep** | **16** | **18** | **23** | +5 |

**PR25 verdict:** each deep topic independently fills its own Top4 — `tpn` and
`agent_acceleration` regain their 4th slot that global competition (B) had starved, and
`storage_media` gets its own 3 slots without taking any from another topic. `dpu_inline`
has 0 because no qualified candidates exist in the frozen input for that topic this run
(allowed: N=0 ⇒ 0 deep).

## 3. TPN comparison (the topic PR20 was designed to fix)

| # | A: Original (tech=None) | B: PR20–24 | C: PR25 |
|---|---|---|---|
| 1 | vllm v0.25.0 (rel 130) | AAFLOW+ (93 / tech 19) | AAFLOW+ (93 / 19) |
| 2 | ExpertPlex (113.6) | KV-cache scheduler (72 / 16) | TensorCast (92 / 19) |
| 3 | AAFLOW+ (105.6) | An Internet for KV (73 / 16) | Load-Aware Prefill / Kairos (86 / 17) |
| 4 | Alibaba WAIC (103.6) | — | An Internet for KV (73 / 16) |
| — | — | vllm v0.25.0 **REJECTED** (rel 22 / tech 6) | vllm v0.25.0 **REJECTED** |

- **vllm v0.25.0 (a routine release) stays correctly suppressed** in both B and C (it was
  erroneously deep in A via the deterministic rule-match bypass). PR20's fix holds under PR25.
- C promotes **TensorCast (tech 19)** and **Kairos (tech 17)** into TPN Top4 — both were
  `DEFERRED_FETCH`/stub-fact in B (fulltext not previously extracted) and only complete in C
  after the corrupted fact-cache entries were cleaned (see §8). This is the clearest evidence
  that PR25 topic-local Top4 surfaces more genuine high-tech papers per topic.

## 4. storage_media (validates PR23 topic + PR25 routing)

C is the **first run with a genuine storage-media deep set** (A and B had 0 — the frozen
input contained no real media papers; B was collected pre-PR23).

| Rank | Title | Direction | rel | tech | Source |
|---:|---|---|---:|---:|---|
| 1 | SK hynix/SanDisk first open HBF standard (OCP) | flash_nand_hbf | 92 | **20** | news.skhynix.com |
| 2 | Kioxia/SanDisk 10th-gen 332-layer QLC NAND (>37 Gb/mm², 4.8 Gb/s) | flash_nand_hbf | 88 | 16 | sandisk.com newsroom |
| 3 | SK hynix V10 375-layer 4D NAND (FMS 2026) | flash_nand_hbf | 78 | 14 | news.skhynix.com |

- All three are **A-level primary** vendor sources with **correct original-source titles**
  (no discovery-brand leak), all within the 60-day freshness window (2026-08-04..07).
- `emerging_nvm`, `magnetic_recording`, `media_controller_codesign` have **0 fresh primary**
  candidates in the window (foundry MRAM = late-2025; HAMR stories = Feb–Mar 2026; ZNS/FTL
  arXiv = 2024–25). Uneven distribution is honest and allowed.
- No mis-routing into ai_chip / memory_dsa / dpu_inline (the HBF item's secondary
  `media_controller_codesign` match was correctly REJECTED on the topic boundary).

## 5. Reader-facing quality (all three pass)

| Check | A | B | C |
|---|:-:|:-:|:-:|
| Standalone 项目影响 removed / merged into 本期判断 | (pre-PR22: had it) | ✅ | ✅ |
| No internal selection-metadata leak | (pre-PR22) | ✅ | ✅ |
| No discovery-source brand leak (AI HOT / YeeKal) | ⚠️ patched post-hoc | ✅ (root-cause) | ✅ (root-cause) |
| Deep items show original paper/source title | (pre-PR22) | ✅ | ✅ |
| Radar is technical signals, not article list | article-centric | ✅ signal-centric | ✅ signal-centric |
| Renderer validation failures | 0 | 0 | 0 |

---

## 6. Real executor token attribution (PR26)

Tokens come from Claude Code `message.usage` records (not character proxies). All four
components are kept separate; `total_tokens` is a usage-volume sum, **not** a dollar bill.

| Metric | A: Original | B: PR20–24 | C: PR25+Media |
|---|---:|---:|---:|
| input_tokens | 1,984,620 | 1,914,135 | 707,334 |
| cache_creation_input_tokens | 0 | 0 | 0 |
| cache_read_input_tokens | 33,859,968 | 60,296,896 | 38,708,266 |
| output_tokens | 443,791 | 255,115 | 279,447 |
| **total_tokens** | **36,288,379** | **62,466,146** | **39,697,047** ⚠️ |
| host tokens | 27,315,727 | 55,391,410 | 36,961,325 ⚠️ |
| agent tokens | 8,972,652 | 7,074,736 | **2,735,722** |
| agent sessions | 59 | 25 | 8 |
| retry sessions | 1 | 4 | 0 |
| error / 429 records | 1 | 7 | 0 |
| cache_share_of_context | 94.5% | 96.9% | 98.2% |
| agent_read_chars_proxy | 1,815,182 | 972,451 | (low — cache-reuse) |

⚠️ **C host tokens are a LOWER BOUND.** The three runs share one Claude Code host session
(`c87757ec…`) that was **compacted** mid-run-C at 2026-08-09T04:29Z. Records after the
compaction point (the bulk of run-C's host orchestration — fork, all advances, batch
assembly, dispatch) had not been flushed to the session JSONL at import time. C's **agent**
tokens (2.7M, 8 sessions) are complete; C's **host** tokens (34.7M) cover only the
pre-compaction window. A and B are fully archived (their numbers are complete).

`cache_creation_input_tokens = 0` across all three: the prefix cache was already warm from
prior sessions / carried by the harness, so nearly all context reads are `cache_read`, not
`cache_creation`.

### Host windows used (explicit, with rationale)

- **A (original):** 2026-08-08T12:02:57Z → 14:39:10Z — first briefing host action through
  end of the original run's dedicated session snapshot (before PR/debug work).
- **B (PR20–24 replay):** 2026-08-08T14:39:10Z → 2026-08-09T01:24:06Z — **includes the
  PR20–24 coding/debug/test work**, which could not be cleanly separated from replay
  execution inside one session. This *inflates* B's host number; treat B-host as an upper
  bound on "replay execution" host cost (see §7).
- **C (PR25+media):** 2026-08-09T01:24:06Z → (live); pre-compaction portion only (caveat above).

---

## 7. Why was the PR20–24 replay (B) more expensive than the original (A)?

**Data-driven answer, ranked by measured contribution to Δ(B−A) = +26.18M tokens:**

| # | Driver | Δ tokens | % of Δ |
|---:|---|---:|---:|
| 1 | **host cache_read** rose 33.86M → 60.30M | **+26.43M** | **+101%** of Δ |
| 2 | host tokens overall 27.32M → 55.39M | +28.08M | (overlaps #1) |
| 3 | agent tokens **fell** 8.97M → 7.07M | −1.90M | −7% |
| 4 | output tokens fell 444K → 255K | −0.19M | −1% |
| 5 | input_tokens flat (1.98M → 1.91M) | −0.07M | ~0% |

**Conclusion: the replay's extra cost is essentially 100% host prefix-cache reads, not
Agent work.** Agent tokens and sessions actually *decreased* (59 → 25 sessions).

What this means concretely:
- B's host session window was **~11 h** (14:39 → 01:24) vs A's **~2.6 h** (12:02 → 14:39).
  Each host turn re-reads the ever-growing session prefix. More turns (coding + debugging +
  replay orchestration) × larger prefix ⇒ `cache_read` accumulates linearly with
  (turns × prefix-size). At ~96.9% cache share, almost every context token is a cache read.
- B also paid 4 retry sessions + 7 error/429 records (the rate-limit + invalid-output
  retries noted in the PR20–24 report) — but these are a *small* fraction (agent-scope,
  and retry sessions overlap the agent total).
- **The single biggest lever is NOT "fewer agents" — it is "fewer/shorter host turns on a
  long shared session."** A replay done in a fresh, short host session (or with the host
  context trimmed) would not pay the 11h of prefix re-reads.

**What does NOT explain it (correcting priors):**
- ❌ "More agents" — agent tokens/sessions went *down*.
- ❌ "The Harness" as an independent number — cannot be separated from native usage; the
  harness cost shows up *as* the host cache_read volume (host turns), not as a line item.
- ❌ "Re-collection" — there was none; raw items are identical.

## 8. Harness contribution (B)

> **Cannot be precisely isolated.** Native `message.usage` does not separate
  system/harness tokens from model tokens. What can be said from the data: B's excess is
  concentrated in `host` scope `cache_read` (+26.4M), i.e. the host turn loop (which is the
  harness/host orchestration reading the long session prefix). Agent-scope tokens (the
  actual subagent inference) went down. So the harness/host loop is *where* the extra tokens
  are, but we do not fabricate a standalone "harness = N tokens" figure.

## 9. Prefix cache — did it help?

- `cache_read_input_tokens` is large in all runs (94–98% of context). So the prefix cache
  is hit on nearly every turn — **but cache-read tokens are usage volume, billed/read at a
  discount, not zero-cost.** "Cache hit" and "zero cost" are different things.
- `cache_creation_input_tokens = 0` everywhere ⇒ no new cache was *created* during these
  runs; the prefix was already warm (carried across sessions by the harness). So the cache
  avoided *re-creation* cost but each turn still pays *cache-read* volume proportional to
  prefix size.
- Net: the cache prevents `cache_creation` spend (good) but does **not** prevent the
  linear growth of `cache_read` as the host session grows. That growth is exactly what made
  B expensive.

## 10. Retry attribution (PR26 stable task-id based)

| Run | retry sessions | retry total tokens | dominant retry stage |
|---|---:|---:|---|
| A | 1 | ~minimal | item writing |
| B | 4 | included in agent 7.07M | item_writing_batch (the rate-limit + invalid-output retries) |
| C | 0 | 0 | — |

B's 4 retry sessions are the `item_writing_batch` re-dispatches documented in the PR20–24
report (429 rate-limit + invalid outputs). As a share of B's total they are modest
(agent-scope, ≤ a few hundred K) — **retry is NOT the main driver** of B's cost; the host
cache_read growth is.

## 11. Business-agent count vs Claude-Code usage (kept separate)

| | A | B | C |
|---|---:|---:|---:|
| Pipeline relevance tasks | 22 | 6 | 7 |
| Pipeline fact tasks (deep) | 16 | 18 | 23 |
| **Actual Claude subagent sessions** | 59 | 25 | 8 |
| **Actual agent-scope tokens** | 8.97M | 7.07M | 2.73M |

"Agent task count ↓ ⇒ tokens ↓" is **false in general** (A had more pipeline relevance
tasks but B had fewer sessions yet cost more overall, because host scope dominates). The
correct unit is **tokens by scope/stage**, not task count.

C's agent sessions (8) are far below A (59) and B (25) precisely because the 616's
relevance/Technology-Value/item/fact-check were reused deterministically and the fact cache
replayed — so C only spawned agents for genuinely-new semantic work (media + PR25-newly-deep
+ synthesis). **Average tokens/agent-session: A≈152K, B≈283K, C≈342K** (C's sessions read
large fulltexts for fact extraction, hence higher per-session).

---

## 12. Findings & caveats (honest)

1. **Corrupted fact_cache (cleaned, not code-fixed).** 10 of 24 `fact_cache` rows were
   fixture-stubs (`condition: "offline fixture"`, `"不代表真实论文性能数据"`) created
   2026-08-08 for real arXiv papers. They fed stub "facts" to PR25-newly-deep candidates.
   We **deleted the 10 polluted rows** (data hygiene on a corrupted cache) and re-extracted
   those facts from cached fulltext — the resulting items are real and evidence-grounded.
   This is a real data-integrity finding worth a permanent guard (out of scope: no product
   code changed).
2. **C host tokens are a lower bound** (compaction gap, §6). The agent side is complete.
3. **B's host window includes PR20–24 development**, so B-host (and thus B-total) is an
   upper bound on pure replay-execution cost.
4. **storage_media is exercised (3 deep)** but only in `flash_nand_hbf`; the other 3
   directions had no fresh primary in the 60-day window (honest, not fabricated).
5. **3 minor repairs skipped** in C (precision gaps on q84 facts) — gaps retained, documented.

## 13. Top token-optimization directions (data says; NOT implemented — no PR27)

1. **Run replays in a fresh / trimmed host session.** The #1 cost driver is host
   `cache_read` growth on a long shared session (+26.4M in B). A replay CLI that doesn't
   drag an 11h host prefix would cut the dominant cost. (Largest expected win.)
2. **Compact/segment the host context between pipeline stages** so each `advance` turn
   re-reads a smaller prefix. Targets the same linear `cache_read` growth.
3. **Widen content-keyed cache reuse to non-eligible sources** (the 616 reuse done
   deterministically here is exactly this, done out-of-band; making `_cache_eligible`
   less restrictive, or adding a "prior identical-content judgment" fast path, would let
   the pipeline reuse without manual orchestration). Cuts agent sessions further.

(These are recommendations from the data only; none implemented per task constraints.)

## Artifacts (run C)

- `email.html`, `review.html`, `validation.json` (0 fail / 0 warn / 13 pass)
- `issue/synthesis.json` (3 judgements, 5 radar signals, 4 project_insights for traceability)
- `media-search-audit.md`, `executor-usage-{original,replay-pr20-24,replay-pr25-media}.json`
- `media-fulltext/` (3 pre-fetched primary fulltexts, reused offline)
- This file: `three-run-comparison.md`
