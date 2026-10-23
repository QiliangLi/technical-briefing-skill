# Published briefing archive

This directory contains the public, reader-facing history of sent briefings. `archive/index.json` is the ordered issue index. Each date has one stable directory under `archive/issues/<date>/`.

```text
archive/
├── index.json
└── issues/<date>/
    ├── email.html
    ├── email-illustrated.html
    ├── issue.json
    ├── reader.json
    ├── papers.json
    ├── publication-manifest.json
    └── original/
```

The files at the issue root are the current public reader projection. `original/` keeps immutable generated or sent snapshots. A migration may update the root reader files, but it must not overwrite an existing original snapshot.

## Publication rules

- A successful `python briefing.py send --confirm-send` archives the active run and attempts to publish it.
- Mail transport and archive publication have separate states. If mail succeeded but publication failed, use `python briefing.py publish-archive --run <run_id>`; do not resend.
- Re-running archive or publication commands with unchanged inputs must be idempotent.
- `publication-manifest.json` binds the reader artifacts by hash.
- Recipient-visible images must use stable absolute URLs. Local workspace paths and relative run paths are forbidden.
- `archive/index.json` must be rebuilt after adding or migrating an issue.

## Manual maintenance

The low-level archive tool supports a completed run and bounded historical reader migration.

```bash
python scripts/archive_sent_issue.py archive --run <run_id>
python scripts/archive_sent_issue.py prepare-rewrite --date <date> --output <input.json>
python scripts/archive_sent_issue.py apply-rewrite --date <date> --input <reader-output.json>
```

Use the normal `send` and `publish-archive` commands for current runs. The migration commands exist for historical repairs and keep their own validation and provenance requirements.

## `papers.json`

`papers.json` is the issue-level source index used by the public knowledge views. Its stable `paper_key` supports cross-issue joins. `role` is one of `core`, `supplement`, or `radar`; source identity, issue date, topic, item ID, score, and source level remain available for audit and aggregation.
