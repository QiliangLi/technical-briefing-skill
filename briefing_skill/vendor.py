from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .utils import now_iso, read_json, write_json


class VendorManager:
    def __init__(self, root: Path):
        self.root = root
        self.lock = read_json(root / "vendor-lock.json", {})

    def install(self, *, update: bool = False) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for name, spec in self.lock.items():
            path = self.root / spec["path"]
            if path.exists() and (path / ".git").exists():
                if update:
                    subprocess.run(["git", "-C", str(path), "fetch", "--all", "--prune"], check=True)
                    subprocess.run(["git", "-C", str(path), "checkout", spec.get("ref", "main")], check=True)
                    subprocess.run(["git", "-C", str(path), "pull", "--ff-only"], check=True)
            elif path.exists():
                shutil.rmtree(path)
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["git", "clone", "--depth", "1", "--branch", spec.get("ref", "main"), spec["repository"], str(path)], check=True)
            commit = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
            records.append({"name": name, "path": spec["path"], "commit": commit, "installed_at": now_iso(), "license_note": spec.get("license_note")})
        write_json(self.root / "vendor-installed.json", {"installed": records})
        return records
