"""Idea cards: pick a few ideas, say them in plain language, send them, count the verdicts.

A card is the one message the assistant sends that nobody asked for in the
moment. It leaves only through ``feedback push --confirm-send``, at most once
a week and at most three per push. The buttons and reactions on a card are the
feedback, and a reconciliation against Feishu repairs what the event stream
missed.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..utils import read_json
from . import lark, outbox, tasks
from .config import AssistantConfig
from .constants import CARD_CHOICES, CARD_REACTIONS, CARDS_PER_PUSH, PUSH_INTERVAL_DAYS, REVIVE_AFTER_DAYS
from .store import Store
from .timeutil import iso

STATUS_LABELS = {"ready_for_validation": "可验证", "observing": "观察中", "seed": "种子"}
# Registry rows whose placeholder gave way to the real message ID once the card went out.
NOT_PENDING = "message_id NOT LIKE ?"


class FeedbackError(RuntimeError):
    pass


# ---- choosing ----


def load_ideas(root: Path) -> dict[str, dict[str, Any]]:
    """Every published idea by ID."""

    ideas: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "knowledge" / "ideas").glob("*.json")):
        idea = read_json(path, {})
        if isinstance(idea, dict) and idea.get("idea_id"):
            ideas[idea["idea_id"]] = idea
    return ideas


def _moved(idea: dict[str, Any], issue: str) -> bool:
    """The idea's status changed in this issue."""
    return any(
        entry.get("issue_date") == issue and entry.get("to_status") != entry.get("from_status")
        for entry in idea.get("decision_log") or []
    )


def _changed(idea: dict[str, Any], issue: str) -> bool:
    """A status change or new evidence recorded for this issue."""
    if _moved(idea, issue):
        return True
    evidence = [*(idea.get("evidence_for") or []), *(idea.get("evidence_against") or [])]
    return any(item.get("issue_date") == issue for item in evidence)


def _priority(idea: dict[str, Any], issue: str) -> tuple[int, int, str]:
    """A status change outranks new evidence, a mature idea outranks a seed, then the ID keeps it stable."""

    rank = list(STATUS_LABELS).index(idea.get("status")) if idea.get("status") in STATUS_LABELS else len(STATUS_LABELS)
    return (not _moved(idea, issue), rank, idea["idea_id"])


def select(
    ideas: dict[str, dict[str, Any]],
    answered: set[str],
    pushed: dict[str, str],
    issue: str,
    limit: int = CARDS_PER_PUSH,
) -> dict[str, list[str]]:
    """Which ideas to show for an issue.

    What changed in this issue comes first, then what is new in it, then at
    most one old idea nobody has answered, the one shown longest ago. An idea
    shown less than a week before is left out entirely, and an unanswered one
    is not revived until it has rested for ``REVIVE_AFTER_DAYS``.
    """

    day = date.fromisoformat(issue)
    recent, rested = str(day - timedelta(days=PUSH_INTERVAL_DAYS)), str(day - timedelta(days=REVIVE_AFTER_DAYS))
    resting = {idea_id for idea_id, sent in pushed.items() if sent > recent}
    eligible = [idea_id for idea_id in ideas if idea_id not in resting]
    changed = {idea_id for idea_id in eligible if _changed(ideas[idea_id], issue)}
    created = {idea_id for idea_id in eligible if ideas[idea_id].get("first_seen_issue") == issue} - changed
    quiet = [
        idea_id for idea_id in eligible
        if idea_id not in changed and idea_id not in created and idea_id not in answered and pushed.get(idea_id, "") < rested
    ]
    revived = sorted(quiet, key=lambda idea_id: (idea_id not in pushed, pushed.get(idea_id, ""), idea_id))[:1]
    ordered = [sorted(group, key=lambda idea_id: _priority(ideas[idea_id], issue)) for group in (changed, created)]
    return {"changed": ordered[0], "created": ordered[1], "revived": revived, "selected": (ordered[0] + ordered[1] + revived)[:limit]}


# ---- the card ----


def _cut(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def stored_copy(idea: dict[str, Any]) -> dict[str, Any]:
    """The card's wording until the host session has written the plain-language copy."""

    evidence = next((item.get("reason") for item in idea.get("evidence_for") or [] if item.get("reason")), "暂无已发布的证据")
    return {
        "headline": _cut(idea.get("title", ""), 40),
        "summary": _cut(f"{idea.get('problem', '')} {idea.get('hypothesis', '')}", 120),
        "why_it_matters": _cut(idea.get("expected_effect", ""), 100),
        "evidence": _cut(evidence, 120),
        "source": "stored",
    }


def for_session(idea: dict[str, Any]) -> dict[str, Any]:
    """What the host session may read of an idea to write its copy."""

    return {
        "idea_id": idea["idea_id"], "title": idea.get("title", ""), "status": idea.get("status", ""),
        "problem": idea.get("problem", ""), "hypothesis": idea.get("hypothesis", ""), "mechanism": idea.get("mechanism", ""),
        "expected_effect": idea.get("expected_effect", ""), "first_seen_issue": idea.get("first_seen_issue", ""),
        "evidence": [item.get("reason", "") for item in (idea.get("evidence_for") or [])[:3]],
    }


def card(idea: dict[str, Any], copy: dict[str, Any], site_base_url: str) -> dict[str, Any]:
    """One idea as the group will see it; the link is built from the published site."""

    first_seen = idea.get("first_seen_issue") or ""
    return {
        "idea_id": idea["idea_id"],
        "headline": copy["headline"],
        "summary": copy["summary"],
        "why_it_matters": copy["why_it_matters"],
        "evidence": stored_copy(idea)["evidence"],
        "status": STATUS_LABELS.get(idea.get("status", ""), idea.get("status", "")) + (f"，{first_seen} 起" if first_seen else ""),
        "url": f"{site_base_url}#ideas?idea={idea['idea_id']}",
        "copy": copy.get("source", "stored"),
    }


def card_json(item: dict[str, Any]) -> str:
    """The card as Feishu card JSON 1.0: text blocks, then one button per verdict."""

    blocks = [
        item["summary"],
        f"**为什么重要**：{item['why_it_matters']}",
        f"**一条代表证据**：{item['evidence']}",
        f"**状态**：{item['status']}　[查看详情]({item['url']})",
    ]
    buttons = [
        {
            "tag": "button", "text": {"tag": "plain_text", "content": label}, "type": "primary" if index == 0 else "default",
            "value": {"choice": choice, "idea": item["idea_id"]},
        }
        for index, (choice, label) in enumerate(CARD_CHOICES.items())
    ]
    elements = [{"tag": "div", "text": {"tag": "lark_md", "content": block}} for block in blocks]
    elements += [
        {"tag": "hr"},
        {"tag": "div", "text": {"tag": "lark_md", "content": "你怎么看？点一个按钮，也可以在这张卡片的话题里讨论。"}},
        {"tag": "action", "actions": buttons},
    ]
    header = {"title": {"tag": "plain_text", "content": item["headline"]}, "template": "blue"}
    return json.dumps({"config": {"wide_screen_mode": True}, "header": header, "elements": elements}, ensure_ascii=False)


# ---- prepare and push ----


def prepare(
    root: Path, config: AssistantConfig, state_dir: Path, store: Store, issue: str, now: float
) -> dict[str, Any]:
    """Choose the ideas of an issue and make sure plain-language copy is on the way for each."""

    ideas = load_ideas(root)
    if not ideas:
        raise FeedbackError("No ideas under knowledge/ideas; run the knowledge stage first")
    pushed: dict[str, str] = {}
    for row in store.fetchall(f"SELECT idea_id, issue_date FROM registry WHERE {NOT_PENDING}", (outbox.PENDING_CARD + "%",)):
        pushed[row["idea_id"]] = min(pushed.get(row["idea_id"], row["issue_date"]), row["issue_date"])
    answered = {row["idea_id"] for row in store.fetchall("SELECT DISTINCT idea_id FROM feedback WHERE idea_id IS NOT NULL")}
    selection = select(ideas, answered, pushed, issue)

    drafts = store.get_meta("card_drafts", {})
    copy_tasks = []
    with store.transaction() as connection:
        for idea_id in selection["selected"]:
            if idea_id in drafts:
                continue
            thread_key = f"card:{issue}:{idea_id}"
            queued = connection.execute(
                "SELECT 1 FROM tasks WHERE kind='card_copy' AND thread_key=? AND status IN ('pending', 'applied')", (thread_key,)
            ).fetchone()
            created = (
                None if queued else tasks.create(
                    connection, state_dir, kind="card_copy", payload={"idea": for_session(ideas[idea_id])},
                    policy_version="", now=now, thread_key=thread_key,
                )
            )
            if created:
                copy_tasks.append(created["task_id"])
    cards = []
    for idea_id in selection["selected"]:
        copy = {**drafts[idea_id], "source": "session"} if idea_id in drafts else stored_copy(ideas[idea_id])
        cards.append(card(ideas[idea_id], copy, config.site_base_url))
    return {
        "issue": issue,
        "chat_id": config.chat_whitelist[0] if config.chat_whitelist else None,
        "selection": selection,
        "cards": cards,
        "copy_tasks": copy_tasks,
        "waiting_for_copy": [item["idea_id"] for item in cards if item["copy"] == "stored"],
    }


def push(
    root: Path, config: AssistantConfig, state_dir: Path, store: Store, issue: str, transport: Any, *, confirm: bool, now: float
) -> dict[str, Any]:
    """Show what would be sent; send it only when confirmed, and never twice for one issue."""

    plan = prepare(root, config, state_dir, store, issue, now)
    prefix = f"card:{issue}:"
    fresh = [item for item in plan["cards"] if store.fetchone("SELECT 1 FROM outbox WHERE id=?", (prefix + item["idea_id"],)) is None]
    report = {**plan, "sent": [], "already_sent": [item["idea_id"] for item in plan["cards"] if item not in fresh]}
    if not confirm:
        return {**report, "note": "Preview only; nothing was sent. Add --confirm-send to send these cards."}
    if not fresh:
        return report
    if not config.chat_whitelist:
        return {**report, "error": "No group is whitelisted; run `python briefing.py assistant chat add <chat_id>` first"}
    last = store.fetchone(
        f"SELECT MAX(issue_date) AS issue_date FROM registry WHERE {NOT_PENDING} AND issue_date <> ?", (outbox.PENDING_CARD + "%", issue)
    )
    if last and last["issue_date"] and date.fromisoformat(issue) - date.fromisoformat(last["issue_date"]) < timedelta(days=PUSH_INTERVAL_DAYS):
        earliest = date.fromisoformat(last["issue_date"]) + timedelta(days=PUSH_INTERVAL_DAYS)
        return {**report, "error": f"Cards were pushed for issue {last['issue_date']}; the next push is for an issue on or after {earliest}"}

    chat_id = config.chat_whitelist[0]
    with store.transaction() as connection:
        for item in fresh:
            key = prefix + item["idea_id"]
            connection.execute(
                "INSERT OR IGNORE INTO registry(message_id, idea_id, issue_date, pushed_at) VALUES(?, ?, ?, ?)",
                (outbox.PENDING_CARD + key, item["idea_id"], issue, iso(now)),
            )
            outbox.enqueue(
                store, connection, key=key, kind="card", chat_id=chat_id, reply_to="", text=card_json(item), thread_key=None, now=now
            )
    outbox.flush(store, transport, now)
    states = {
        row["id"][len(prefix):]: row["status"]
        for row in store.fetchall(f"SELECT id, status FROM outbox WHERE substr(id, 1, ?) = ?", (len(prefix), prefix))
    }
    report["delivery"] = states
    report["sent"] = [idea_id for idea_id, state in states.items() if state == "sent"]
    return report


# ---- counting ----


def collect(store: Store, client: Any, now: float) -> dict[str, Any]:
    """Make the ledger agree with the reactions Feishu shows on every sent card."""

    added = removed = unreadable = 0
    cards = store.fetchall(f"SELECT message_id, idea_id FROM registry WHERE {NOT_PENDING}", (outbox.PENDING_CARD + "%",))
    for row in cards:
        try:
            live = client.reactions(row["message_id"])
        except lark.LarkError:  # reported rather than treated as "no reactions"
            unreadable += 1
            continue
        wanted = set()
        for item in live:
            operator = (item.get("operator") or {}).get("operator_id") or ""
            choice = CARD_REACTIONS.get(((item.get("reaction_type") or {}).get("emoji_type")) or "")
            if operator and choice:
                wanted.add((operator, choice))
        known = {
            (entry["operator_id"], entry["choice"])
            for entry in store.fetchall("SELECT operator_id, choice FROM feedback WHERE message_id=? AND source='reaction'", (row["message_id"],))
        }
        with store.transaction() as connection:
            for operator, choice in sorted(wanted - known):
                connection.execute(
                    "INSERT OR IGNORE INTO feedback(id, message_id, idea_id, choice, operator_id, source, created_at) VALUES(?, ?, ?, ?, ?, 'reaction', ?)",
                    (f"{row['message_id']}:{operator}:{choice}", row["message_id"], row["idea_id"], choice, operator, iso(now)),
                )
                added += 1
            for operator, choice in sorted(known - wanted):
                removed += connection.execute(
                    "DELETE FROM feedback WHERE message_id=? AND operator_id=? AND choice=? AND source='reaction'",
                    (row["message_id"], operator, choice),
                ).rowcount
    return {"cards": len(cards), "added": added, "removed": removed, "unreadable": unreadable}


def summary(store: Store) -> dict[str, Any]:
    """Verdicts per idea, and when cards went out."""

    tallies: dict[str, dict[str, Any]] = {}
    for row in store.fetchall("SELECT * FROM feedback WHERE idea_id IS NOT NULL"):
        tally = tallies.setdefault(row["idea_id"], {**dict.fromkeys(CARD_CHOICES, 0), "people": set()})
        tally[row["choice"]] = tally.get(row["choice"], 0) + 1
        tally["people"].add(row["operator_id"])
    return {
        "ideas": {
            idea_id: {**{name: count for name, count in tally.items() if name != "people"}, "people": len(tally["people"])}
            for idea_id, tally in sorted(tallies.items())
        },
        "pushes": store.fetchall(
            f"SELECT issue_date, COUNT(*) AS cards, MIN(pushed_at) AS pushed_at FROM registry WHERE {NOT_PENDING} GROUP BY issue_date ORDER BY issue_date",
            (outbox.PENDING_CARD + "%",),
        ),
        "unsent_cards": store.fetchone("SELECT COUNT(*) AS n FROM registry WHERE message_id LIKE ?", (outbox.PENDING_CARD + "%",))["n"],
    }
