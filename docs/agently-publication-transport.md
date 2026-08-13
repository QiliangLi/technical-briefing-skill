# Agently publication transport

The production briefing delivery path has one transport owner: Agently CLI.

A completed illustrated issue is sendable only when every reader-facing `<img>` uses a public HTTPS URL. Generated explanatory images are written under `published-assets/<run_id>/`, committed and pushed, and represented in the illustration manifest by a commit-SHA-pinned `raw.githubusercontent.com` URL. Local filesystem paths and branch-name URLs are not publication artifacts.

The exact final `email-illustrated.html` is passed to Agently both as `--body-file` and as `--attachment`. The same two-step confirmation-token flow remains in effect. Direct SMTP is retired from the active runtime so body rendering, attachments, confirmation, and sent-history handoff cannot diverge across transport implementations.

## Atomicity boundary

Agently delivery and local SQLite recording are not one distributed transaction. The remote send completes first; `_record_sent` then atomically commits the local `send_history`, issue/run state, canonical `published_sources`, and compatibility projections in one database transaction. If the remote send succeeds but the local transaction fails, `publication-sync` / Sent-mailbox reconciliation is the recovery path. In this project, “atomic publication history” therefore means atomic **post-send local database state**, not atomicity of the remote send plus database pair.
