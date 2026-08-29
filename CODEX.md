# Codex usage

1. Read `AGENTS.md` and `SKILL.md`.
2. Start or resume a run, then execute only the bounded work returned by `python briefing.py tasks next --run latest`.
3. For `illustrated_publication`, use Codex image generation after reading the project persona overlay and manifest named by the task.
4. Preserve the text-only email when image generation fails. Do not substitute another persona or illustration style.
5. Never send mail without explicit user confirmation and `--confirm-send`. The default `agently-cli` backend uses a second confirmation call after it displays the send summary.
