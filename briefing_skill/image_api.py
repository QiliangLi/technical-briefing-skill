"""OpenAI-compatible image-generation API client for briefing illustrations.

This module is the deterministic transport for the API image-generation host
path described in ``docs/contracts/illustrated-publication.md``. It never
decides what to draw; prompt construction, persona references, and QA stay
with the ``illustrated_publication`` executor.

Endpoints are tried in configured order with per-endpoint retries. The API
key is read from the git-ignored secret file or the environment and is never
embedded in configuration, code, logs, or task outputs.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

DEFAULT_ENDPOINTS: list[dict[str, str]] = [
    {"name": "main", "base_url": "https://code1.newcli.com", "path_prefix": "/v1"},
    {"name": "backup", "base_url": "https://code2.newcli.com", "path_prefix": "/v1"},
    {"name": "cn_optimized", "base_url": "https://dm-fox.rjj.cc", "path_prefix": "/codex/v1"},
]

SECRET_PATH = Path("workspace/secrets/image_api.json")
ENV_KEY = "BRIEFING_IMAGE_API_KEY"


class ImageAPIError(RuntimeError):
    """Raised when every endpoint failed to produce one image."""


@dataclass
class ImageAPIConfig:
    model: str = "gpt-image-2.5"
    size: str = "1536x1024"
    quality: str = "high"
    timeout_seconds: int = 300
    retries_per_endpoint: int = 2
    retry_backoff_seconds: float = 3.0
    endpoints: list[dict[str, str]] = field(default_factory=lambda: list(DEFAULT_ENDPOINTS))

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "ImageAPIConfig":
        raw = (settings or {}).get("image_api") or {}
        cfg = cls()
        cfg.model = str(raw.get("model") or cfg.model)
        cfg.size = str(raw.get("size") or cfg.size)
        cfg.quality = str(raw.get("quality") or cfg.quality)
        cfg.timeout_seconds = int(raw.get("timeout_seconds") or cfg.timeout_seconds)
        cfg.retries_per_endpoint = int(raw.get("retries_per_endpoint") or cfg.retries_per_endpoint)
        cfg.retry_backoff_seconds = float(raw.get("retry_backoff_seconds") or cfg.retry_backoff_seconds)
        endpoints = raw.get("endpoints")
        if isinstance(endpoints, list) and endpoints:
            merged: list[dict[str, str]] = []
            for entry in endpoints:
                if isinstance(entry, dict) and entry.get("base_url"):
                    merged.append({
                        "name": str(entry.get("name") or entry["base_url"]),
                        "base_url": str(entry["base_url"]).rstrip("/"),
                        "path_prefix": str(entry.get("path_prefix") or "/v1"),
                    })
            if merged:
                cfg.endpoints = merged
        return cfg


def load_api_key(root: Path, override: str | None = None) -> str:
    if override:
        return override
    env = os.environ.get(ENV_KEY)
    if env:
        return env
    secret_file = root / SECRET_PATH
    if secret_file.is_file():
        try:
            data = json.loads(secret_file.read_text(encoding="utf-8"))
            key = data.get("api_key")
            if isinstance(key, str) and key.strip():
                return key.strip()
        except (OSError, json.JSONDecodeError):
            pass
    raise ImageAPIError(
        f"image API key not found: set {ENV_KEY} or create {SECRET_PATH} with {{\"api_key\": \"...\"}}"
    )


def _decode_b64_images(payload: dict[str, Any]) -> list[bytes]:
    images: list[bytes] = []
    for entry in payload.get("data") or []:
        b64 = entry.get("b64_json") if isinstance(entry, dict) else None
        if not b64:
            continue
        try:
            images.append(base64.b64decode(b64))
        except (binascii.Error, ValueError):
            continue
    return images


def _request_image(
    endpoint: dict[str, str],
    api_key: str,
    prompt: str,
    references: list[Path],
    cfg: ImageAPIConfig,
    timeout: int,
) -> bytes:
    base = endpoint["base_url"].rstrip("/") + endpoint.get("path_prefix", "/v1").rstrip("/")
    if references:
        url = f"{base}/images/edits"
        files: list[tuple[str, tuple[str, bytes, str]]] = []
        for ref in references:
            data = Path(ref).read_bytes()
            mime = "image/png" if str(ref).lower().endswith(".png") else "image/jpeg"
            files.append(("image", (Path(ref).name, data, mime)))
        form = [
            ("model", cfg.model),
            ("prompt", prompt),
            ("size", cfg.size),
            ("quality", cfg.quality),
            ("response_format", "b64_json"),
        ]
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            data=form,
            files=files,
            timeout=timeout,
        )
    else:
        url = f"{base}/images/generations"
        body = {
            "model": cfg.model,
            "prompt": prompt,
            "size": cfg.size,
            "quality": cfg.quality,
            "n": 1,
        }
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )
    if resp.status_code != 200:
        raise ImageAPIError(f"{url} returned HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise ImageAPIError(f"{url} returned non-JSON body: {resp.text[:200]}") from exc
    images = _decode_b64_images(payload)
    if not images:
        raise ImageAPIError(f"{url} returned no b64_json image data: {str(payload)[:200]}")
    return images[0]


def generate_image(
    prompt: str,
    output_path: str | Path,
    root: Path,
    settings: dict[str, Any] | None = None,
    reference_images: list[str | Path] | None = None,
    api_key_override: str | None = None,
    config_override: ImageAPIConfig | None = None,
) -> Path:
    """Generate one image and write it to ``output_path``.

    Returns the written path. Raises :class:`ImageAPIError` when all endpoints
    and retries fail; the caller decides whether to skip the illustration.
    """
    cfg = config_override or ImageAPIConfig.from_settings(settings or {})
    api_key = load_api_key(root, api_key_override)
    references = [Path(p) for p in (reference_images or [])]
    for ref in references:
        if not ref.is_file():
            raise ImageAPIError(f"reference image not found: {ref}")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    for endpoint in cfg.endpoints:
        for attempt in range(cfg.retries_per_endpoint + 1):
            try:
                image_bytes = _request_image(endpoint, api_key, prompt, references, cfg, cfg.timeout_seconds)
                out.write_bytes(image_bytes)
                return out
            except (ImageAPIError, requests.RequestException, OSError) as exc:
                errors.append(f"{endpoint['name']}#{attempt}: {exc}")
                if attempt < cfg.retries_per_endpoint:
                    time.sleep(cfg.retry_backoff_seconds)
    raise ImageAPIError("all image API endpoints failed: " + " | ".join(errors[-6:]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate one briefing illustration via the image API.")
    parser.add_argument("--prompt-file", required=True, help="UTF-8 text file containing the full image prompt.")
    parser.add_argument("--out", required=True, help="Output PNG path (repository relative or absolute).")
    parser.add_argument("--ref", action="append", default=[], help="Reference image for /images/edits; repeatable.")
    parser.add_argument("--size", default=None, help="Override configured size, e.g. 1536x1024.")
    parser.add_argument("--quality", default=None, help="Override configured quality.")
    parser.add_argument("--model", default=None, help="Override configured model id.")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    from .config import ConfigBundle  # noqa: WPS433  local import keeps CLI optional
    from .paths import Paths  # noqa: WPS433

    settings = ConfigBundle.load(Paths(root)).settings
    cfg = ImageAPIConfig.from_settings(settings)
    if args.size:
        cfg.size = args.size
    if args.quality:
        cfg.quality = args.quality
    if args.model:
        cfg.model = args.model
    try:
        path = generate_image(
            prompt=prompt,
            output_path=args.out,
            root=root,
            settings=settings,
            reference_images=args.ref,
            config_override=cfg,
        )
    except ImageAPIError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "path": str(path), "bytes": path.stat().st_size}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
