from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .config import ConfigBundle
from .db import Database
from .http import HttpClient
from .utils import chunk_text, now_iso, stable_hash, write_json

LOGGER = logging.getLogger(__name__)


class FulltextService:
    def __init__(self, config: ConfigBundle, db: Database, run_dir: Path):
        self.config = config
        self.db = db
        self.run_dir = run_dir
        self.http = HttpClient(
            timeout=float(config.settings.get("http_timeout_seconds", 25)),
            user_agent=config.settings.get("http_user_agent", "TechnicalBriefingSkill/0.1"),
        )

    def close(self) -> None:
        self.http.close()

    def fetch_candidate(self, run_id: str, candidate: dict) -> dict:
        raw = self.db.fetchone("SELECT * FROM raw_items WHERE id=?", (candidate["raw_item_id"],))
        if not raw:
            raise KeyError(candidate["raw_item_id"])
        url = raw.get("original_url") or raw.get("canonical_url") or raw.get("aihot_url")
        document_id = stable_hash(run_id, candidate["id"], url)
        text_path = self.run_dir / "documents" / f"{document_id}.md"
        status, media_type, error = "FETCHED", "text/plain", None
        payload = __import__("json").loads(raw.get("payload_json") or "{}")
        try:
            if payload.get("local_fulltext_path"):
                source_path = Path(str(payload["local_fulltext_path"]))
                root = self.run_dir.parents[2].resolve()
                candidates = [source_path] if source_path.is_absolute() else [self.run_dir / source_path, root / source_path]
                resolved = next(
                    (
                        path.resolve()
                        for path in candidates
                        if path.resolve().is_relative_to(root) and path.is_file()
                    ),
                    None,
                )
                if not resolved:
                    raise FileNotFoundError(f"Local fulltext not found: {source_path}")
                text = resolved.read_text(encoding="utf-8")
                status, media_type = "LOCAL_SOURCE", "text/markdown"
            elif payload.get("fixture"):
                text = self._fallback_text(raw)
                media_type = "text/plain"
            else:
                text, media_type = self._fetch(url, raw)
        except Exception as exc:
            LOGGER.warning("Fulltext failed %s: %s", url, exc)
            text = self._fallback_text(raw)
            status, error = "FALLBACK", str(exc)
        max_chars = int(self.config.settings.get("max_fulltext_chars", 140000))
        # PDF extractors occasionally return lone UTF-16 surrogate code points.
        # They are valid Python string contents but cannot be encoded as UTF-8,
        # which used to abort the whole run while writing the document. Replace
        # only those invalid code points and preserve the rest of the source text.
        text = self._sanitize_text(text)[:max_chars]
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(text, encoding="utf-8")
        chunks = chunk_text(
            text,
            int(self.config.settings.get("fact_chunk_chars", 28000)),
            int(self.config.settings.get("fact_chunk_overlap_chars", 1200)),
        )
        chunk_paths: list[str] = []
        for idx, chunk in enumerate(chunks, 1):
            path = self.run_dir / "documents" / "chunks" / f"{document_id}-{idx:02d}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(chunk, encoding="utf-8")
            chunk_paths.append(str(path))
        manifest = {
            "document_id": document_id,
            "candidate_id": candidate["id"],
            "url": url,
            "media_type": media_type,
            "fetch_status": status,
            "text_path": str(text_path),
            "chunks": chunk_paths,
            "char_count": len(text),
            "error": error,
        }
        write_json(self.run_dir / "documents" / f"{document_id}.json", manifest)
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents(
                    id, run_id, candidate_id, url, media_type, text_path,
                    char_count, fetch_status, error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    run_id,
                    candidate["id"],
                    url,
                    media_type,
                    str(text_path),
                    len(text),
                    status,
                    error,
                    now_iso(),
                ),
            )
        return manifest

    def _fetch(self, url: str, raw: dict) -> tuple[str, str]:
        if not url:
            raise ValueError("No original URL")
        payload = __import__("json").loads(raw.get("payload_json") or "{}")
        preferred = payload.get("pdf_url") or url
        response = self.http.get(preferred)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "pdf" in content_type or preferred.lower().endswith(".pdf"):
            return self._extract_pdf(response.content), "application/pdf"
        return self._extract_html(response.text, preferred), "text/html"

    @staticmethod
    def _extract_pdf(content: bytes) -> str:
        reader = PdfReader(io.BytesIO(content))
        pages: list[str] = []
        for index, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            pages.append(f"\n\n## PDF Page {index}\n\n{text}")
        result = "".join(pages).strip()
        if not result:
            raise ValueError("PDF contains no extractable text")
        return result

    @staticmethod
    def _extract_html(html: str, url: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside", "form", "noscript", "svg"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else url
        main = soup.find("article") or soup.find("main") or soup.body or soup
        blocks: list[str] = [f"# {title}\n", f"Source: {url}\n"]
        for node in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "pre", "table"]):
            text = node.get_text(" ", strip=True)
            if not text or len(text) < 2:
                continue
            if node.name.startswith("h"):
                level = min(int(node.name[1]), 4)
                blocks.append(f"{'#' * level} {text}")
            elif node.name == "li":
                blocks.append(f"- {text}")
            else:
                blocks.append(text)
        result = "\n\n".join(blocks)
        result = re.sub(r"\n{3,}", "\n\n", result)
        if len(result) < 300:
            raise ValueError("HTML extraction too short")
        return result

    @staticmethod
    def _fallback_text(raw: dict) -> str:
        return (
            f"# {raw.get('title','Untitled')}\n\n"
            f"Source: {raw.get('original_url') or raw.get('aihot_url') or ''}\n\n"
            f"## Available summary\n\n{raw.get('summary') or ''}\n"
        )

    @staticmethod
    def _sanitize_text(text: str) -> str:
        return text.encode("utf-8", errors="replace").decode("utf-8")
