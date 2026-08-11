import json
from pathlib import Path


TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".txt", ".cjs", ".html"}
SKIP_DIRS = {".git", ".pytest_cache", "__pycache__", "vendor", "workspace"}


def _repository_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield path


def test_retired_writing_skill_name_is_absent_from_repository_contracts() -> None:
    root = Path(__file__).resolve().parents[1]
    retired_name = "human" + "izer"
    offenders = []
    for path in _repository_text_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if retired_name in text.lower():
            offenders.append(str(path.relative_to(root)))
    assert offenders == []


def test_vendor_lock_keeps_only_social_card_dependency() -> None:
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / "vendor-lock.json").read_text(encoding="utf-8"))
    assert set(lock) == {"guizang-social-card-skill"}


def test_top_level_skill_uses_ian_reference_manifest_only() -> None:
    root = Path(__file__).resolve().parents[1]
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "ian-xiaohei-illustrations" in skill
    assert "assets/persona/ian-qiliang/overlay.md" in skill
    assert "assets/persona/ian-qiliang/reference-manifest.yaml" in skill
    assert "assets/persona/reference.jpg" not in skill
