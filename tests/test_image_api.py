import base64
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from briefing_skill.image_api import (
    ENV_KEY,
    ImageAPIConfig,
    ImageAPIError,
    generate_image,
    load_api_key,
)

PNG_BYTES = b"\x89PNG-fake-bytes-for-test"


def _b64_png() -> str:
    return base64.b64encode(PNG_BYTES).decode()


def _ok_response():
    class Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"data": [{"b64_json": _b64_png()}]}

    return Resp()


def test_config_defaults_and_overrides():
    cfg = ImageAPIConfig.from_settings({})
    assert cfg.model == "gpt-image-2.5"
    assert cfg.size == "1536x1024"
    assert [e["name"] for e in cfg.endpoints] == ["main", "backup", "cn_optimized"]
    assert cfg.endpoints[-1]["base_url"] == "https://dm-fox.rjj.cc"

    settings = {
        "image_api": {
            "model": "gpt-image-9",
            "endpoints": [{"name": "only", "base_url": "https://example.test/"}],
        }
    }
    cfg2 = ImageAPIConfig.from_settings(settings)
    assert cfg2.model == "gpt-image-9"
    assert cfg2.endpoints == [{"name": "only", "base_url": "https://example.test", "path_prefix": "/v1"}]


def test_api_key_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    secret = tmp_path / "workspace/secrets/image_api.json"
    secret.parent.mkdir(parents=True)
    secret.write_text(json.dumps({"api_key": "  sk-file  "}), encoding="utf-8")
    assert load_api_key(tmp_path) == "sk-file"
    monkeypatch.setenv(ENV_KEY, "sk-env")
    assert load_api_key(tmp_path) == "sk-env"
    assert load_api_key(tmp_path, "sk-override") == "sk-override"
    monkeypatch.delenv(ENV_KEY, raising=False)
    with pytest.raises(ImageAPIError):
        load_api_key(tmp_path / "nowhere")


def test_generate_image_generations_endpoint(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    secret = tmp_path / "workspace/secrets/image_api.json"
    secret.parent.mkdir(parents=True)
    secret.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")

    calls = []

    def fake_post(url, headers=None, json=None, data=None, files=None, timeout=None):
        calls.append({"url": url, "json": json, "files": files})
        return _ok_response()

    cfg = ImageAPIConfig(retries_per_endpoint=0)
    out = tmp_path / "out.png"
    with patch("briefing_skill.image_api.requests.post", side_effect=fake_post):
        path = generate_image("a prompt", out, tmp_path, {}, config_override=cfg)

    assert path == out
    assert out.read_bytes() == PNG_BYTES
    assert len(calls) == 1
    assert calls[0]["url"] == "https://code1.newcli.com/v1/images/generations"
    assert calls[0]["json"]["model"] == "gpt-image-2.5"
    assert calls[0]["json"]["prompt"] == "a prompt"


def test_generate_image_edits_uses_references(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    secret = tmp_path / "workspace/secrets/image_api.json"
    secret.parent.mkdir(parents=True)
    secret.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")

    ref = tmp_path / "anchor.png"
    ref.write_bytes(b"anchor")
    calls = []

    def fake_post(url, headers=None, json=None, data=None, files=None, timeout=None):
        calls.append({"url": url, "data": data, "files": files})
        return _ok_response()

    cfg = ImageAPIConfig(retries_per_endpoint=0)
    out = tmp_path / "out2.png"
    with patch("briefing_skill.image_api.requests.post", side_effect=fake_post):
        generate_image("edit prompt", out, tmp_path, {}, reference_images=[ref], config_override=cfg)

    assert calls[0]["url"] == "https://code1.newcli.com/v1/images/generations".replace(
        "generations", "edits"
    )
    assert ("response_format", "b64_json") in calls[0]["data"]
    assert len(calls[0]["files"]) == 1
    assert calls[0]["files"][0][0] == "image"


def test_failover_across_endpoints(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    secret = tmp_path / "workspace/secrets/image_api.json"
    secret.parent.mkdir(parents=True)
    secret.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")

    state = {"n": 0}

    def fake_post(url, **kwargs):
        state["n"] += 1
        if state["n"] <= 2:
            class Bad:
                status_code = 502
                text = "bad gateway"

            return Bad()
        return _ok_response()

    cfg = ImageAPIConfig(retries_per_endpoint=0, retry_backoff_seconds=0)
    out = tmp_path / "out3.png"
    with patch("briefing_skill.image_api.requests.post", side_effect=fake_post), patch(
        "briefing_skill.image_api.time.sleep"
    ):
        generate_image("p", out, tmp_path, {}, config_override=cfg)

    assert out.read_bytes() == PNG_BYTES
    assert state["n"] == 3


def test_all_endpoints_failing_raises(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    secret = tmp_path / "workspace/secrets/image_api.json"
    secret.parent.mkdir(parents=True)
    secret.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")

    def fake_post(url, **kwargs):
        class Bad:
            status_code = 500
            text = "nope"

        return Bad()

    cfg = ImageAPIConfig(retries_per_endpoint=0)
    with patch("briefing_skill.image_api.requests.post", side_effect=fake_post):
        with pytest.raises(ImageAPIError, match="all image API endpoints failed"):
            generate_image("p", tmp_path / "x.png", tmp_path, {}, config_override=cfg)


def test_missing_reference_image_is_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_KEY, raising=False)
    secret = tmp_path / "workspace/secrets/image_api.json"
    secret.parent.mkdir(parents=True)
    secret.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")
    with pytest.raises(ImageAPIError, match="reference image not found"):
        generate_image(
            "p",
            tmp_path / "x.png",
            tmp_path,
            {},
            reference_images=[tmp_path / "missing.png"],
            config_override=ImageAPIConfig(retries_per_endpoint=0),
        )
