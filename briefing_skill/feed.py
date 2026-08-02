from __future__ import annotations

from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree as ET


@dataclass
class FeedEntry:
    title: str = ""
    link: str = ""
    summary: str = ""
    published: str | None = None
    updated: str | None = None
    id: str = ""
    author: str = ""
    authors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)


def parse_feed(content: bytes | str) -> list[FeedEntry]:
    if isinstance(content, str):
        content = content.encode("utf-8")
    root = ET.fromstring(content)
    name = _local(root.tag)
    if name == "feed":
        return _parse_atom(root)
    if name == "rss":
        return _parse_rss(root)
    if name == "RDF":
        return _parse_rss(root)
    return []


def _parse_atom(root: ET.Element) -> list[FeedEntry]:
    entries: list[FeedEntry] = []
    for node in [child for child in root if _local(child.tag) == "entry"]:
        links = []
        for link in node:
            if _local(link.tag) == "link":
                links.append({k: v for k, v in link.attrib.items()})
        preferred = ""
        for link in links:
            if link.get("rel", "alternate") == "alternate" and link.get("href"):
                preferred = link["href"]
                break
        if not preferred:
            preferred = next((link.get("href", "") for link in links if link.get("href")), "")
        authors = []
        for author in [child for child in node if _local(child.tag) == "author"]:
            authors.append(_text(_find(author, "name")))
        entries.append(
            FeedEntry(
                title=_text(_find(node, "title")),
                link=preferred,
                summary=_text(_find(node, "summary")) or _text(_find(node, "content")),
                published=_text(_find(node, "published")) or None,
                updated=_text(_find(node, "updated")) or None,
                id=_text(_find(node, "id")),
                author=authors[0] if authors else "",
                authors=[a for a in authors if a],
                tags=[child.attrib.get("term", "") for child in node if _local(child.tag) == "category"],
                links=links,
            )
        )
    return entries


def _parse_rss(root: ET.Element) -> list[FeedEntry]:
    items = [node for node in root.iter() if _local(node.tag) == "item"]
    result = []
    for node in items:
        result.append(
            FeedEntry(
                title=_text(_find(node, "title")),
                link=_text(_find(node, "link")),
                summary=_text(_find(node, "description")) or _text(_find(node, "encoded")),
                published=_text(_find(node, "pubDate")) or _text(_find(node, "date")) or None,
                updated=_text(_find(node, "updated")) or None,
                id=_text(_find(node, "guid")),
                author=_text(_find(node, "author")) or _text(_find(node, "creator")),
            )
        )
    return result


def _find(node: ET.Element, local_name: str) -> ET.Element | None:
    for child in node.iter():
        if child is node:
            continue
        if _local(child.tag) == local_name:
            return child
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()
