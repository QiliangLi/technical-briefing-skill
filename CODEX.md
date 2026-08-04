# Codex usage

1. Read `SKILL.md`.
2. Run `python briefing.py run` or `resume`.
3. Use `python briefing.py tasks next` and complete one task at a time.
4. For illustration tasks, use available image generation only after reading the vendored Guizang Material Illustration instructions.
5. Do not send email without explicit user confirmation and `--confirm-send`. The default backend is `agently-cli`, which has its own two-phase confirmation token; after the first call, stop and wait for the user's confirmation before rerunning the command.
