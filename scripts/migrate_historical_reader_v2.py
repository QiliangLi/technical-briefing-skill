from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ARCHIVE_DATES = (
    "2026-08-02",
    "2026-08-06",
    "2026-08-10",
    "2026-08-11",
    "2026-08-15",
    "2026-08-17",
)

NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])\d+(?:\.\d+)?")
BOUNDARY_TERMS = ("但", "不过", "仍", "尚未", "没有", "未覆盖", "缺少", "局限", "只覆盖", "仅")
RESULT_TERMS = (
    "提升", "降低", "下降", "提高", "加速", "吞吐", "时延", "准确率", "命中率", "成本", "倍", "%", "ms", "秒",
)
SCHEDULING_TERMS = ("调度", "路由", "偏转", "队列", "准入", "放置", "选择传输", "重算")
CACHE_TERMS = ("KV", "缓存", "Cache", "cache", "前缀", "逐出", "命中")
CODE_TERMS = ("代码", "仓库", "索引", "符号", "调用链", "检索Agent", "Read", "Grep")
ENGINEERING_TERMS = ("release", "Release", "版本", "轮子", "CUDA", "ROCm", "驱动", "API", "接口", "发布")

PREFIX_REWRITES = (
    ("值得借鉴的是", "可先验证"),
    ("值得参考的是", "可先验证"),
    ("可以把它作为", "可先将其作为"),
    ("可把它作为", "可先将其作为"),
    ("可以用它", "可用于"),
    ("它适合作为", "更适合作为"),
    ("可用作", "可用于"),
    ("可以先把", "可先把"),
)


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split()).strip()


def _naturalise(text: Any) -> str:
    value = _clean(text)
    for old, new in PREFIX_REWRITES:
        if value.startswith(old):
            value = new + value[len(old) :]
            break
    return value


def _numbers(value: Any) -> set[str]:
    return set(NUMBER_RE.findall(str(value or "")))


def _heading_key(text: str, item: dict[str, Any], *, from_takeaway: bool = False) -> str | None:
    if from_takeaway:
        return "boundary" if any(term in text for term in BOUNDARY_TERMS) else "implication"

    direction = str(item.get("direction_id") or "")
    topic = str(item.get("topic_id") or "")
    combined = f"{direction} {topic} {text}"

    # Results often contain their own caveat. Prefer the evidence role when the
    # paragraph reports measured numbers; the caveat remains visible in the text.
    if any(term in text for term in RESULT_TERMS) and re.search(r"\d", text):
        return "result"
    if any(term in text for term in BOUNDARY_TERMS):
        return "boundary"
    if any(term in combined for term in SCHEDULING_TERMS):
        return "scheduling"
    if any(term in combined for term in CODE_TERMS):
        return "code_relation"
    if any(term in combined for term in CACHE_TERMS):
        return "cache"
    if any(term in combined for term in ENGINEERING_TERMS):
        return "engineering"
    return "mechanism"


def migrate_item(item: dict[str, Any]) -> dict[str, Any]:
    """Reproject an already fact-safe historical rewrite into the Reader v2 shape.

    Historical archives were previously rewritten semantically, but the result was
    persisted as a fixed lead/body/takeaway template. This migration keeps those
    grounded facts, removes the routine takeaway slot from dense cards, and persists
    one explicit block sequence so future rerenders never infer structure again.
    """

    lead = _naturalise(item.get("lead"))
    body = [_naturalise(value) for value in item.get("body") or [] if _naturalise(value)]
    takeaway = _naturalise(item.get("takeaway"))

    candidates: list[tuple[str, bool]] = []
    if lead:
        candidates.append((lead, False))
    candidates.extend((text, False) for text in body[:2])

    # A short legacy card often stored its only actionable boundary as takeaway.
    # Preserve that information when there is room. Dense cards intentionally omit
    # the repetitive fourth-slot conclusion: Reader v2 is selective, not lossless.
    if takeaway and len(candidates) < 3:
        candidates.append((takeaway, True))

    if not candidates:
        raise ValueError(f"historical item has no reader prose: {item.get('title')}")

    blocks: list[dict[str, str | None]] = []
    for index, (text, from_takeaway) in enumerate(candidates[:3]):
        blocks.append(
            {
                "heading_key": None if index == 0 else _heading_key(text, item, from_takeaway=from_takeaway),
                "text": text,
            }
        )

    legacy_numbers = _numbers(
        "\n".join(
            [
                str(item.get("title") or ""),
                str(item.get("lead") or ""),
                *(str(value or "") for value in item.get("body") or []),
                str(item.get("takeaway") or ""),
            ]
        )
    )
    block_numbers = _numbers("\n".join(str(block["text"]) for block in blocks))
    invented = sorted(block_numbers - legacy_numbers)
    if invented:
        raise ValueError(f"historical v2 migration introduced numbers: {invented}")

    migrated = dict(item)
    migrated["blocks"] = blocks
    # Compatibility fields mirror the durable blocks. This also removes the old
    # universal takeaway slot rather than letting legacy renderers reintroduce it.
    migrated["lead"] = str(blocks[0]["text"])
    migrated["body"] = [str(block["text"]) for block in blocks[1:]]
    migrated["takeaway"] = None
    return migrated


def migrate_reader(reader: dict[str, Any]) -> dict[str, Any]:
    if reader.get("rewrite_status") != "historical_semantic_rewrite":
        raise ValueError("only historical_semantic_rewrite documents may be migrated")
    migrated = dict(reader)
    migrated["items"] = {
        str(item_id): migrate_item(dict(item))
        for item_id, item in (reader.get("items") or {}).items()
    }
    return migrated


def _render_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def migrate_archives(root: Path, *, check: bool = False) -> list[Path]:
    changed: list[Path] = []
    for issue_date in ARCHIVE_DATES:
        path = root / "archive" / "issues" / issue_date / "reader.json"
        reader = json.loads(path.read_text(encoding="utf-8"))
        rendered = _render_json(migrate_reader(reader))
        current = path.read_text(encoding="utf-8")
        if current == rendered:
            continue
        changed.append(path)
        if not check:
            path.write_text(rendered, encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when committed archives are not v2-migrated")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    changed = migrate_archives(root, check=args.check)
    if args.check and changed:
        for path in changed:
            print(path.relative_to(root))
        return 1
    for path in changed:
        print(path.relative_to(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
