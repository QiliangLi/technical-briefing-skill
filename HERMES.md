# Hermes usage

Read `AGENTS.md` and `SKILL.md` first. The pipeline is provider-neutral and only requires file access plus shell execution for ordinary tasks.

Hermes must follow the exact input and output paths returned by `python briefing.py tasks next --run latest`. If the host lacks image generation or web search for a task that explicitly requires it, use the task's documented failure or text-only fallback. Do not widen the evidence scope or silently replace the requested capability.
