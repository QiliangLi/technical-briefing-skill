from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def prompts(self) -> Path:
        return self.root / "prompts"

    @property
    def schemas(self) -> Path:
        return self.root / "schemas"

    @property
    def templates(self) -> Path:
        return self.root / "templates"

    @property
    def workspace(self) -> Path:
        return self.root / "workspace"

    @property
    def runs(self) -> Path:
        return self.workspace / "runs"

    @property
    def archive(self) -> Path:
        return self.workspace / "archive"

    @property
    def logs(self) -> Path:
        return self.workspace / "logs"

    @property
    def db(self) -> Path:
        return self.workspace / "briefing.sqlite"

    @property
    def vendor(self) -> Path:
        return self.root / "vendor"

    def ensure(self) -> None:
        for path in (self.workspace, self.runs, self.archive, self.logs, self.vendor):
            path.mkdir(parents=True, exist_ok=True)


def discover_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "SKILL.md").exists() and (candidate / "config" / "topics.yaml").exists():
            return candidate
    return Path(__file__).resolve().parents[1]
