# Agently publication transport

The production briefing delivery path has one transport owner: Agently CLI.

A completed illustrated issue is sendable only when every reader-facing `<img>` uses a public HTTPS URL. Generated explanatory images are written under `published-assets/<run_id>/`, committed and pushed, and represented in the illustration manifest by a commit-SHA-pinned `raw.githubusercontent.com` URL. Local filesystem paths and branch-name URLs are not publication artifacts.

The exact final `email-illustrated.html` is passed to Agently both as `--body-file` and as `--attachment`. The same two-step confirmation-token flow remains in effect. Direct SMTP is retired from the active runtime so body rendering, attachments, confirmation, and sent-history handoff cannot diverge across transport implementations.
