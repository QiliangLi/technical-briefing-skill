# Implementation Status — v0.1.0

## Implemented

- Portable `SKILL.md` workflow for Claude Code, Codex, Hermes, and other shell-capable Agents.
- Unified CLI: setup, doctor, collect, Agent web-search tasks, relevance review, fact extraction, fact check, event clustering, item writing, issue synthesis, visual routing, rendering, validation, review, approval, send, and resume.
- SQLite persistence for runs, source ETags, raw items, candidates, tasks, facts, events, issue items, approvals, and send history.
- AI HOT v1 adapter with ETag support, original-link preservation, and elevated query/score priority for AI, Agent, KVCache, and inference-system topics.
- arXiv, RSS/Atom, GitHub Release, Agent web-search, and offline fixture adapters.
- Multi-stage context control: metadata filter first, one source per full-text task, structured facts downstream.
- URL/title/content/event-level deduplication and incremental-update rules.
- 300–450 Chinese-character item contract, independent fact-check task, 4–6 item issue selection, and two-item-per-topic cap.
- Visual routing and deterministic SVG chart generation for exact numeric data.
- Guizang Material Illustration task briefs and Guizang Social Card adapter with a self-contained fallback renderer.
- HTML email, local review page, explicit approval gate, agently-cli two-phase confirmation gate, SMTP fallback, and CID image embedding for the SMTP path.
- Optional personal “技术侦察员” specification. A real likeness is only used after an approved reference image is placed at `assets/persona/reference.jpg`.
- Offline end-to-end demo and automated tests.

## Verified in this build

- `python -m compileall -q briefing_skill scripts`
- `pytest -q`: 27 tests passed.
- Offline end-to-end demo reached `AWAITING_APPROVAL`.
- Headless approval rebuilt the issue and email with status `APPROVED`.
- Live collection completed with 130 raw items, 17 high-relevance items, and 6 selected brief items.
- Guizang card rendering generated PNG assets through Playwright.
- Validation completed with no failures.

## Not executed in this runtime

- Image-model generation: intentionally delegated to the current Agent so the Skill remains model-independent.
- Live mail delivery: requires a locally authenticated `agently-cli` account and explicit recipient confirmation; SMTP remains available only when `EMAIL_BACKEND=smtp`.

## First local test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python briefing.py setup --vendor --node
python briefing.py doctor
python briefing.py demo
```

Then open the latest run's `email.html` and `cards/index.html`.

## Known tuning points

- Add or remove sources in `config/sources.yaml`.
- Tune AI HOT priority and query breadth in `config/topics.yaml`.
- Replace topic context cards with project-specific questions and evidence requirements.
- Adjust scoring thresholds after observing a few real runs.
- Add the approved persona reference photo only when personal-likeness illustrations are desired.
- Review the upstream licenses before distributing or modifying vendor code. Guizang Social Card states AGPL-3.0; Guizang Material Illustration did not expose a `LICENSE` file at the time checked, so obtain explicit license clarity before redistribution.
