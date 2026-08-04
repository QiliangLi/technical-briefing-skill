from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from dateutil import parser as date_parser


TRACKING_QUERY_PREFIXES = ("utm_", "spm", "ref", "source", "campaign")
TOKEN_RE = re.compile(r"[A-Za-z0-9_+.#-]+|[\u4e00-\u9fff]{1,8}")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _dotenv_value(raw_value: str, line_number: int) -> str:
    value = raw_value.lstrip()
    if not value:
        return ""
    if value[0] == "'":
        end = value.find("'", 1)
        if end < 0:
            raise RuntimeError(f"Invalid .env syntax on line {line_number}: unterminated single quote")
        tail = value[end + 1 :].strip()
        if tail and not tail.startswith("#"):
            raise RuntimeError(f"Invalid .env syntax on line {line_number}: unexpected text after quoted value")
        return value[1:end]
    if value[0] == '"':
        decoded: list[str] = []
        escaped = False
        end = -1
        escape_map = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"'}
        for index, char in enumerate(value[1:], 1):
            if escaped:
                decoded.append(escape_map.get(char, f"\\{char}"))
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                end = index
                break
            else:
                decoded.append(char)
        if end < 0:
            raise RuntimeError(f"Invalid .env syntax on line {line_number}: unterminated double quote")
        tail = value[end + 1 :].strip()
        if tail and not tail.startswith("#"):
            raise RuntimeError(f"Invalid .env syntax on line {line_number}: unexpected text after quoted value")
        return "".join(decoded)

    comment_at = next(
        (index for index, char in enumerate(value) if char == "#" and (index == 0 or value[index - 1].isspace())),
        len(value),
    )
    return value[:comment_at].strip()


def load_root_env(root: Path) -> None:
    """Load root/.env without overriding the current process environment."""
    if os.environ.get("BRIEFING_SKIP_DOTENV", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    path = root / ".env"
    if not path.exists():
        return
    parsed: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "export" or line.startswith("export ") or line.startswith("export\t"):
            line = line[6:].lstrip()
        if "=" not in line:
            raise RuntimeError(f"Invalid .env syntax on line {line_number}: expected KEY=VALUE")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not ENV_KEY_RE.fullmatch(key):
            raise RuntimeError(f"Invalid .env key on line {line_number}")
        parsed[key] = _dotenv_value(raw_value, line_number)
    for key, value in parsed.items():
        os.environ.setdefault(key, value)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = date_parser.parse(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def canonicalize_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower = key.lower()
        if any(lower.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        query.append((key, value))
    clean_path = re.sub(r"/{2,}", "/", parts.path or "/")
    if clean_path != "/":
        clean_path = clean_path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), clean_path, urlencode(query), ""))


def source_identity_key(url: str | None, external_id: str | None = None) -> str:
    """Return a stable source identity across title, language, and arXiv-version changes."""
    canonical = canonicalize_url(url)
    parts = urlsplit(canonical) if canonical else None
    host = (parts.hostname or "").lower() if parts else ""
    path = unquote(parts.path or "").strip("/") if parts else ""

    if host in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
        match = re.search(r"(?:abs|pdf)/([^/?#]+)", f"/{path}", flags=re.I)
        if match:
            arxiv_id = re.sub(r"\.pdf$", "", match.group(1), flags=re.I)
            arxiv_id = re.sub(r"v\d+$", "", arxiv_id, flags=re.I)
            return f"arxiv:{arxiv_id.lower()}"

    if host in {"doi.org", "dx.doi.org"} and path:
        return f"doi:{path.lower()}"

    doi_source = f"{external_id or ''} {canonical}"
    doi_match = re.search(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", doi_source, flags=re.I)
    if doi_match:
        return f"doi:{doi_match.group(0).lower().rstrip('.')}"

    if host in {"github.com", "www.github.com"}:
        segments = [segment for segment in path.split("/") if segment]
        if len(segments) >= 5 and segments[2:4] == ["releases", "tag"]:
            return f"github-release:{segments[0].lower()}/{segments[1].lower()}@{'/'.join(segments[4:]).lower()}"
        if len(segments) >= 4 and segments[2] == "commit":
            return f"github-commit:{segments[0].lower()}/{segments[1].lower()}@{segments[3].lower()}"
        if len(segments) == 2:
            return f"github:{segments[0].lower()}/{segments[1].lower()}"

    if canonical:
        return f"url:{canonical}"
    if external_id:
        normalized = normalize_text(external_id)
        if normalized:
            return f"external:{normalized}"
    return ""


def normalize_text(text: str | None) -> str:
    value = unicodedata.normalize("NFKC", text or "").lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\u4e00-\u9fff+.# -]", "", value)
    return value.strip()


def stable_hash(*parts: Any, length: int = 24) -> str:
    payload = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:length]


def content_hash(text: str | None) -> str:
    return stable_hash(normalize_text(text), length=32)


def tokenize(text: str | None) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(normalize_text(text)) if len(token.strip()) > 1}


def jaccard_similarity(a: str | None, b: str | None) -> float:
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def title_similarity(a: str | None, b: str | None) -> float:
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return max(jaccard_similarity(na, nb), _bigram_similarity(na, nb))


def _bigram_similarity(a: str, b: str) -> float:
    def grams(value: str) -> set[str]:
        compact = value.replace(" ", "")
        if len(compact) < 2:
            return {compact}
        return {compact[i : i + 2] for i in range(len(compact) - 1)}

    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return 2 * len(ga & gb) / (len(ga) + len(gb))


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = max(text.rfind("\n#", start, end), text.rfind("\n\n", start, end))
            if boundary > start + size // 2:
                end = boundary
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def setup_logging(log_path: Path | None = None, verbose: bool = False) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_path:
        ensure_parent(log_path)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def unique_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def complete_sentence_excerpt(text: str | None, limit: int) -> str:
    """Compress at sentence/clause boundaries without dangling text or ellipses."""
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return ""
    if len(value) <= limit and re.search(r"[。！？.!?](?:[”’\"）)\]]*)$", value):
        return value
    sentence_boundary = r"(?:[。！？!?]|\.(?!\d)(?=\s|$)|[；;])"
    units = [
        match.group(0).strip()
        for match in re.finditer(rf".+?{sentence_boundary}(?:[”’\"）)\]]*)?", value)
    ]
    if not units:
        return value.rstrip("…，,:：;；、 ") + "。"
    chosen: list[str] = []
    for unit in units:
        candidate = "".join(chosen + [unit])
        if chosen and len(candidate) > limit:
            break
        chosen.append(unit)
        if len(candidate) >= limit:
            break
    result = "".join(chosen).strip()
    if result.endswith(("；", ";")):
        result = result[:-1] + "。"
    return result
