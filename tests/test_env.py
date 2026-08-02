import os
from pathlib import Path

from briefing_skill.cli import main
from briefing_skill.utils import load_root_env


def _minimal_skill_root(root: Path, env_text: str) -> Path:
    (root / "config").mkdir(parents=True)
    (root / "SKILL.md").write_text("# test\n", encoding="utf-8")
    for name, content in {
        "topics.yaml": "topics: []\n",
        "sources.yaml": "sources: []\n",
        "scoring.yaml": "{}\n",
        "settings.yaml": "timezone: Asia/Shanghai\n",
        "email.yaml": "{}\n",
    }.items():
        (root / "config" / name).write_text(content, encoding="utf-8")
    (root / ".env").write_text(env_text, encoding="utf-8")
    return root


def test_load_root_env_parses_supported_syntax_and_preserves_process_env(tmp_path, monkeypatch):
    secret = "test-secret-that-must-not-be-printed"
    (tmp_path / ".env").write_text(
        "\n# comment\nexport ENV_PLAIN=from-file\n"
        "ENV_SINGLE='left=right # literal'\n"
        'ENV_DOUBLE="line\\nwith=equals" # comment\n'
        "ENV_UNQUOTED=left=right # comment\nENV_EMPTY=\n"
        f"ENV_SECRET={secret}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ENV_PLAIN", "from-process")
    for key in ("ENV_SINGLE", "ENV_DOUBLE", "ENV_UNQUOTED", "ENV_EMPTY", "ENV_SECRET"):
        monkeypatch.delenv(key, raising=False)

    load_root_env(tmp_path)

    assert os.getenv("ENV_PLAIN") == "from-process"
    assert os.getenv("ENV_SINGLE") == "left=right # literal"
    assert os.getenv("ENV_DOUBLE") == "line\nwith=equals"
    assert os.getenv("ENV_UNQUOTED") == "left=right"
    assert os.getenv("ENV_EMPTY") == ""
    assert os.getenv("ENV_SECRET") == secret


def test_cli_loads_env_from_discovered_root_outside_root_cwd(tmp_path, monkeypatch, capsys):
    secret = "external-cwd-secret"
    root = _minimal_skill_root(tmp_path / "skill", f"ENV_EXTERNAL_CWD=loaded\nSMTP_PASSWORD={secret}\n")
    nested = root / "outside" / "cwd"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("ENV_EXTERNAL_CWD", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    assert main(["doctor"]) == 0

    output = capsys.readouterr()
    assert os.getenv("ENV_EXTERNAL_CWD") == "loaded"
    assert secret not in output.out
    assert secret not in output.err


def test_cli_root_option_selects_that_roots_env(tmp_path, monkeypatch, capsys):
    secret = "root-option-secret"
    root = _minimal_skill_root(tmp_path / "selected", f"ENV_ROOT_OPTION=loaded\nSMTP_PASSWORD={secret}\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.delenv("ENV_ROOT_OPTION", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    assert main(["--root", str(root), "doctor"]) == 0

    output = capsys.readouterr()
    assert os.getenv("ENV_ROOT_OPTION") == "loaded"
    assert secret not in output.out
    assert secret not in output.err
