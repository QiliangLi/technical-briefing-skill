"""Shared helpers for the group assistant tests.

A tiny published repository, a store, an engine on a fake clock and a transport
that records instead of sending. Tests drive the same code the daemon runs.
"""

from __future__ import annotations

import itertools
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from briefing_skill.assistant import outbox
from briefing_skill.assistant.config import AssistantConfig
from briefing_skill.assistant.constants import CLUSTER_MAX_GAP_SECONDS, DEBOUNCE_SECONDS
from briefing_skill.assistant.engine import Engine
from briefing_skill.assistant.events import Trigger
from briefing_skill.assistant.policy import Policy
from briefing_skill.assistant.retrieval import ensure_index
from briefing_skill.assistant.store import Store
from briefing_skill.paths import discover_root
from briefing_skill.utils import write_json

SITE = "https://example.test/site/"
CHAT = "oc_" + "1" * 32
OTHER_CHAT = "oc_" + "2" * 32
BOT = "ou_bot"
ALICE, BOB = "ou_alice", "ou_bob"
# A Tuesday inside working hours, local time.
BASE = datetime(2026, 10, 6, 10, 0, 0).timestamp()


def _item(item_id: str, title: str, conclusion: str, keywords: list[str]) -> dict:
    return {
        "brief_item_id": item_id,
        "title": title,
        "core_conclusion": conclusion,
        "mechanism": "机制说明。",
        "keywords": keywords,
        "topic_id": "tpn",
        "direction_id": "d1",
    }


ASSET_NAMES = ("assistant-refine", "assistant-contribute", "assistant-card-copy")


def repository(root: Path) -> Path:
    """A miniature of the real checkout: a published corpus, the assistant's own
    prompts and schemas, and decoys that must never be indexed."""

    for name in ASSET_NAMES:
        for folder, suffix in (("prompts", ".md"), ("schemas", ".schema.json")):
            target = root / folder / f"{name}{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(discover_root() / folder / f"{name}{suffix}", target)

    date = "2026-10-01"
    issue_dir = root / "archive" / "issues" / date
    write_json(
        root / "archive" / "index.json",
        {"issues": [{"date": date, "papers_file": f"issues/{date}/papers.json"}]},
    )
    write_json(
        issue_dir / "issue.json",
        {
            "items": [
                _item("a" * 24, "KV cache 分层卸载到内存与 SSD", "把冷 KV 卸载到内存后吞吐提升。", ["KV缓存", "卸载"]),
                _item("b" * 24, "光交换机在智算中心的调度", "按整负载调度光交换机能降低尾延迟。", ["光交换机"]),
            ]
        },
    )
    write_json(
        issue_dir / "papers.json",
        [
            {"paper_key": "radar-1", "title": "液冷 manifold 进入 AI 工厂", "role": "radar", "issue_date": date},
            {"paper_key": "core-1", "title": "KV cache 分层卸载到内存与 SSD", "role": "core", "issue_date": date},
        ],
    )
    write_json(
        root / "knowledge" / "ideas" / "idea_c.json",
        {
            "idea_id": "idea_c",
            "title": "HBF 能否替代 SSD",
            "status": "observing",
            "first_seen_issue": date,
            "problem": "问题。",
            "hypothesis": "假设 HBF 可以替代 SSD。",
            "mechanism": "机制。",
            "topic_ids": ["storage"],
        },
    )
    write_json(
        root / "knowledge" / "roadmaps" / "storage.json",
        {
            "topic_id": "storage",
            "topic_name": "存储介质与器件",
            "summary": "跟踪存储介质。",
            "updated_by_issue": date,
            "branches": [{"name": "HBF", "open_questions": ["成本如何"]}],
        },
    )
    write_json(root / "knowledge" / "idea-candidates" / "cand_1.json", {"title": "DECOYCANDIDATEZX"})
    write_json(root / "workspace" / "runs" / "run-1" / "brief_items" / "x.json", {"title": "DECOYRUNZX"})
    write_json(root / "workspace" / "cache" / "fulltext.json", {"text": "DECOYCACHEZX"})
    return root


class FakeTransport:
    """Records sends. ``failures`` makes the next sends retryable, ``gone`` makes them undeliverable."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []
        self.calls = 0
        self.failures = 0
        self.gone = False

    def send(self, chat_id: str, reply_to: str, text: str, idempotency_key: str, kind: str) -> outbox.SendResult:
        self.calls += 1
        if self.gone:
            return outbox.SendResult("gone", error="message not found")
        if self.failures > 0:
            self.failures -= 1
            return outbox.SendResult("retry", error="network error")
        self.sent.append({"chat_id": chat_id, "reply_to": reply_to, "text": text, "key": idempotency_key, "kind": kind})
        return outbox.SendResult("sent", message_id=f"sent_{idempotency_key}")


class World:
    def __init__(self, tmp_path: Path) -> None:
        self.root = repository(tmp_path / "repo")
        self.state = tmp_path / "state"
        self.now = BASE
        self.ids = itertools.count(1)
        self.config = AssistantConfig(site_base_url=SITE, chat_whitelist=(CHAT,))
        self.index, _ = ensure_index(self.root, self.config, self.state)
        self.store = Store(self.state / "assistant.sqlite")
        self.transport = FakeTransport()
        self.engine = Engine(
            self.store, self.index, self.config, self.root, self.state, bot_ids=(BOT,), clock=lambda: self.now
        )
        self.policy()

    def policy(self, *, explicit: bool = True, proactive: str = "auto") -> Policy:
        policy = Policy(explicit=explicit, proactive=proactive)
        policy.save(self.store)
        return policy

    def trigger(
        self, text: str, *, sender: str = ALICE, mention: bool = False, root: str = "", chat: str = CHAT,
        direct: bool = False, via: str = "event", at: float | None = None, bot: bool | None = None,
        message_id: str | None = None,
    ) -> Trigger:
        moment = self.now if at is None else at
        return Trigger(
            message_id=message_id or f"om_{next(self.ids)}", chat_id=chat, sender_id=sender, created_ms=int(moment * 1000), text=text,
            via=via, root_id=root, is_mention=mention, is_direct=direct, is_bot=(sender == BOT) if bot is None else bot,
        )

    def say(self, text: str, *, advance: float = 1.0, **options: Any) -> dict[str, Any]:
        trigger = self.trigger(text, **options)
        self.now += advance
        return {"message_id": trigger.message_id, **self.engine.ingest(trigger)}

    def resend(self, trigger: Trigger, via: str) -> dict[str, str]:
        return self.engine.ingest(Trigger(**{**trigger.__dict__, "via": via}))

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def new_topic(self) -> None:
        """Move past the clustering window so the next standalone messages form a new discussion."""

        self.advance(CLUSTER_MAX_GAP_SECONDS + 1)

    def flush(self) -> dict[str, int]:
        return outbox.flush(self.store, self.transport, self.now)

    def sent(self) -> list[str]:
        return [item["text"] for item in self.transport.sent]

    def reasons(self, decision: str | None = None) -> set[str]:
        rows = self.store.fetchall("SELECT * FROM dispositions")
        return {row["reason"] for row in rows if decision is None or row["decision"] == decision}

    def tasks(self, status: str = "pending", kind: str | None = None) -> list[dict[str, Any]]:
        rows = self.store.fetchall("SELECT * FROM tasks WHERE status=?", (status,))
        return [row for row in rows if kind is None or row["kind"] == kind]

    def task_input(self, task: dict[str, Any]) -> dict[str, Any]:
        return json.loads(Path(task["input_path"]).read_text(encoding="utf-8"))

    def outbox_rows(self) -> list[dict[str, Any]]:
        return self.store.fetchall("SELECT * FROM outbox ORDER BY created_at, id")

    def discuss(self, lines: list[tuple[str, str]], *, root: str = "", advance: float = 1.0) -> list[dict[str, Any]]:
        """Unaddressed messages from several people inside one discussion."""

        return [self.say(text, sender=sender, root=root, advance=advance) for sender, text in lines]

    def look(self, lines: list[tuple[str, str]], *, root: str = "", proactive: str | None = None) -> dict[str, Any]:
        """Hold a discussion, let the debounce pass and return the look it produces."""

        if proactive is not None:
            self.policy(proactive=proactive)
        if not root:
            self.new_topic()
        self.discuss(lines, root=root)
        self.advance(DEBOUNCE_SECONDS + 1)
        self.engine.sweep()
        looks = self.tasks(kind="contribute")
        assert len(looks) == 1, self.store.fetchall("SELECT decision, reason FROM dispositions")
        return looks[0]

    def speak(self, lines: list[tuple[str, str]], *, root: str = "", act: str = "add") -> dict[str, str]:
        """Take a discussion through a look and send what the stand-in session says; returns what was sent."""

        task = self.look(lines, root=root)
        assert self.apply(task, self.contribution(task, act=act))["outcome"] == "said", self.task_input(task)
        self.flush()
        return self.transport.sent[-1]

    def contribution(self, task: dict[str, Any], *, act: str = "add", doc_id: str | None = None, quote: str | None = None,
                     framing: str | None = None) -> dict[str, Any]:
        """What a host session writes about a discussion: join in with a candidate, or stay silent."""

        payload = self.task_input(task)
        verbatim = payload["messages"][-1]["text"][:6]
        quote = quote or verbatim
        output: dict[str, Any] = {"schema_version": 1, "_task": {"task_id": task["task_id"], "kind": "contribute"}, "act": act}
        if act == "add":
            chosen = doc_id if doc_id is not None else payload["candidates"][0]["id"]
            output.update(framing=framing or "日报库里有一条相关的：", quote=quote, items=[{"doc_id": chosen, "quote": quote}])
        elif act == "review":
            chosen = doc_id if doc_id is not None else payload["candidates"][0]["id"]
            output.update(
                framing=framing or "这个思路和日报库对照的结果：", quote=quote,
                review={"closest_idea": None, "supporting": [{"doc_id": chosen, "quote": quote}], "counter": [], "missing": "库里没有对应内容"},
            )
        elif act == "gap":
            output.update(quote=quote, gap={"summary": "讨论的要点", "nearest": None, "terms": ["新检索词"], "placement": "新建方向"})
        return output

    def careful_contribution(self, task: dict[str, Any], expect_any: list[str]) -> dict[str, Any]:
        """What a careful host session writes: cite the first candidate carrying an expected term, or stay silent."""

        payload = self.task_input(task)
        chosen = next(
            (item for item in payload["candidates"] if any(term in f"{item['title']} {item.get('lead', '')}" for term in expect_any)),
            None,
        )
        return self.contribution(task, act="add" if chosen else "none", doc_id=chosen["id"] if chosen else None)

    def refinement(self, task: dict[str, Any], ids: list[str] | None = None, *, none: bool = False, quote: str | None = None,
                   framing: str = "") -> dict[str, Any]:
        payload = self.task_input(task)
        question = payload["question"]
        chosen = ids if ids is not None else [payload["candidates"][0]["id"]] if payload["candidates"] else []
        output: dict[str, Any] = {
            "schema_version": 1, "_task": {"task_id": task["task_id"], "kind": "refine"}, "queries": ["分层卸载"],
            "selected": [] if none else [{"doc_id": doc_id, "quote": quote or question[:4]} for doc_id in chosen],
            "none_relevant": none,
        }
        if framing:
            output["framing"] = framing
        return output

    def apply(self, task: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        Path(task["output_path"]).write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
        return self.engine.apply_task(task["task_id"], output)
