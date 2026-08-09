# Storage-Media Supplement Search Audit — PR25+Media Replay

**Run:** `2026-08-08-200543-replay-pr25-media`
**Date of search:** 2026-08-09
**Goal:** Add only the *necessary* storage-media raw items so this run can form a real
`storage_media` deep topic, then let the **current main (PR25)** selector decide the
topic's own Top4. No re-collection of the other 8 topics.

## Constraints honored

- Only `storage_media` was searched. No other topic re-collected anything.
- Frozen 616 raw items from `2026-08-08-200543` were forked untouched (`rp2-` ids);
  nothing was written into the original or PR20–24 replay runs.
- The 60-day freshness gate (`absolute_max_age_days=60`, reference 2026-08-09 → floor
  **2026-06-10`) is enforced exactly as the pipeline enforces it. Items older than the
  floor were **not** inserted (no date fabrication). `unknown_published_at` ⇒ exclude.
- Fulltext for the accepted media items was fetched once up front and stored as
  `payload.local_fulltext_path`, so the offline pipeline run reuses it with **zero
  network** (`BRIEFING_OFFLINE_REPLAY=1`). Discovery/secondary sources were leads only;
  every inserted item is an **A-level primary** vendor/research source.

## Directions (per `config/topics-media.yaml`)

`flash_nand_hbf`, `emerging_nvm`, `magnetic_recording`, `media_controller_codesign`.
Uneven distribution is allowed by design ("不要求四个方向平均分布").

## Search queries issued

1. `High Bandwidth Flash HBF AI storage 2026 arxiv OR samsung OR sk hynix`
2. `3D NAND QLC 300 layer density endurance 2026 paper`
3. `HAMR HDD areal density 2026 Seagate Western Digital roadmap demonstration`
4. `STT-MRAM SOT-MRAM embedded non-volatile memory 2026 paper demonstration`
5. `ZNS SSD FTL write amplification controller co-design 2026 paper arxiv`
6. `ReRAM PCM storage class memory device 2026 paper performance endurance`
7. `Flash Memory Summit 2026 August NAND SSD MRAM announcement Samsung Micron Kioxia`
8. `Samsung 9th generation V9 NAND OR 400 layer 2026 …`
9. `SK hynix newsroom V10 375 layer 4D NAND FMS 2026 …`
10. `MRAM mass production 2026 embedded foundry …`
11. `Micron HBF high bandwidth flash OR 232 layer NAND 2026 August …`

## Candidates evaluated

| # | Direction | Primary URL | Date found | Outcome |
|---|---|---|---|---|
| 1 | flash_nand_hbf | https://news.skhynix.com/en/hbf-at-fms-2026/ | 2026-08-04 | **INSERTED** (SK hynix/SanDisk first open HBF standard via OCP: ≤512GB, ≤3TB/s, UCIe; 2.5× power efficiency) |
| 2 | flash_nand_hbf | https://news.skhynix.com/en/fms-2026/ | 2026-08-07 | **INSERTED** (SK hynix V10 375-layer 4D NAND wafer unveiled; 2.5× perf/W) |
| 3 | flash_nand_hbf | https://www.sandisk.com/…/2026-08-04-new-3d-flash-memory-technology… | 2026-08-04 | **INSERTED** (Kioxia/SanDisk 10th-gen 332-layer QLC NAND, >37 Gb/mm², 4.8 Gb/s) |
| 4 | flash_nand_hbf | https://semiconductor.samsung.com/…/samsung-begins-industrys-first-mass-production-of-qlc-9th-gen-v-nand… | no parseable date | SKIP (unknown date ⇒ exclude; not fabricated) |
| 5 | flash_nand_hbf | https://news.samsung.com/global/samsung-unveils-next-gen-3d-memory-vision-at-fms-2026… | n/a | SKIP (news.samsung.com repeatedly timed out / unreachable from the fetch host) |
| 6 | magnetic_recording | https://www.seagate.com/stories/…/seagate-delivers-industrys-highest-capacity-hard-drives… (Mozaic 4+ 44TB HAMR) | 2026-03-03 | SKIP (outside 60-day floor) |
| 7 | magnetic_recording | https://investors.seagate.com/… (Mozaic 4+) | n/a | SKIP (JS-rendered; extraction too short) |
| 8 | flash_nand_hbf | https://www.computer.org/csdl/journal/… (H3 HBM+HBF hybrid paper) | n/a | SKIP (paywalled; extraction too short) |
| 9 | emerging_nvm | ScienceDirect MRAM-in-AI review (2026) | undated | SKIP (no verifiable date ≥ floor) |
| 10 | emerging_nvm | GlobalFoundries AutoPro150 eMRAM 22FDX | ~2025-11 | SKIP (announcement outside 60-day window; volume H2 2026) |
| 11 | media_controller_codesign | arXiv:2511.04687 (ZNS zone-mgmt hidden cost) | 2025-11 | SKIP (outside floor) |
| 12 | media_controller_codesign | arXiv:2410.11260 / 2503.13105 (ZNS / hybrid SSD) | 2024–2025 | SKIP (outside floor) |

## Resulting storage_media topic composition

- **Inserted raw items:** 3 (all `flash_nand_hbf`, all A-level primary, all 2026-08-04..07)
- `emerging_nvm`: **0** fresh primary in the 60-day window (foundry MRAM news was late-2025)
- `magnetic_recording`: **0** fresh primary in the window (HAMR 44TB / WD stories dated Feb–Mar 2026)
- `media_controller_codesign`: **0** fresh primary in the window (ZNS/FTL arXiv work is older)

This is an honest reflection of the window: June–Aug 2026 storage-media activity was
dominated by the Flash Memory Summit 2026 (Aug 4–6) NAND/HBF announcements. Under PR25
topic-local Top4, `storage_media` will receive up to 3 deep slots (N=3 ⇒ 3 deep) and
competes for **no other topic's** slots.

## Why these are competitive Top4 material

Each inserted item carries a concrete, quantified device-level advance (capacity /
bandwidth / density / power-efficiency / layer count) that maps directly onto the
`valuable_evidence` and `current_questions` defined in `topics-media.yaml` — i.e. the
kind of evidence the topic is configured to promote to deep reading rather than radar.

## Raw-item counts

- Frozen raw_items forked from original: **616**
- New `storage_media` raw_items inserted: **3**
- New run raw_items total (before pipeline carryover): **619**
