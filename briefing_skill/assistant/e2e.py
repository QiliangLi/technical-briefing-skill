"""End-to-end checks: a replay that never touches the network, and a live run against the test group.

The live run drives the real resident process on its own state directory and
writes to the group as the user through ``lark-cli --as user``. It is bound to
one group, refuses any other, and every message it writes carries ``[E2E]``.
Where a host session is needed it plays one itself, with output built by rule.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..utils import read_json
from . import lark, outbox
from .config import AssistantConfig, write_local_config
from .constants import QUIET_SECONDS
from .engine import Engine
from .feedback import card, card_json, load_ideas, stored_copy
from .policy import Policy
from .replies import URL, within_limit
from .retrieval import ensure_index
from .store import Store
from .timeutil import iso

LIVE_CHAT = "oc_37c6acf73d9ca25d346146d83c2297c5"
PREFIX = "[E2E]"
CONFIDENT = f"{PREFIX} KV cache 分层卸载怎么做"
UNSURE = f"{PREFIX} 光交换机和 KV 卸载哪个更急"
UNDER_CARD = f"{PREFIX} 这个方向我们组之前试过类似的，有没有先例"
AGAIN = f"{PREFIX} 有没有人做过这个方向"
AFTER_DISLIKE = f"{PREFIX} 再问一句，这一次不该再接话"
REPLAY_SUITES = ("retrieval", "source", "recommend", "tasks", "lark", "service", "commands", "feedback")
READY_TIMEOUT = 60
REPLY_TIMEOUT = 8
QUIET_TIMEOUT = QUIET_SECONDS + 30
SOAK_PROBE_SECONDS = 300
HEARTBEAT_LIMIT = 15
LINK_ID = re.compile(r"#(?:archive\?date=[\d-]+&item=|ideas\?idea=|roadmaps\?topic=)([A-Za-z0-9_]+)")


class E2EError(RuntimeError):
    pass


def replay(root: Path) -> int:
    """The offline suites: events in, a capturing transport out, no network."""

    tests = [str(root / "tests" / f"test_assistant_{name}.py") for name in REPLAY_SUITES]
    return subprocess.call([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests], cwd=root)


def check_chat(chat_id: str | None) -> str:
    """The one group the live run may write into; anything else is refused before any state is touched."""

    if chat_id not in (None, LIVE_CHAT):
        raise E2EError(f"The live run is bound to the test group {LIVE_CHAT} and refuses {chat_id}")
    return LIVE_CHAT


class Live:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.state = root / "workspace" / "assistant-e2e"
        self.config: AssistantConfig
        self.store: Store
        self.engine: Engine
        self.bot_id = ""
        self.process: subprocess.Popen[bytes] | None = None
        self.steps: list[dict[str, Any]] = []

    def run(self) -> dict[str, Any]:
        self._reset()
        report: dict[str, Any] = {"chat_id": LIVE_CHAT, "state_dir": str(self.state), "steps": self.steps}
        try:
            self.step("the published site answers", self.s0_site)
            self.start()
            first = self.step("a mention is answered in its thread within seconds", self.s1_mention)
            self.step("a crash and a restart send nothing twice", lambda: self.s2_crash_restart(first["question"]))
            self.step("a mention inside the thread is answered in that thread", lambda: self.s3_thread(first["question"]))
            self.step("an uncertain question is refined, then answered", self.s4_refine)
            card_message = self.step("a discussion under a card is assessed in observe and nothing is said", self.s5_card_observe)
            self.step("in auto the same discussion gets one recommendation, and a dislike silences it", lambda: self.s6_auto_dislike(card_message))
            self.step("the counts match the scenarios", self.s7_counts)
            report["ok"] = True
        except (E2EError, AssertionError) as exc:
            self.steps.append({"ok": False, "error": str(exc)})
            report["ok"] = False
        finally:
            self.stop()
        return report

    def soak(self, minutes: int) -> dict[str, Any]:
        """Keep the process up for a while, probe it as the user every five minutes and watch its heartbeat."""

        self._reset()
        report: dict[str, Any] = {"chat_id": LIVE_CHAT, "state_dir": str(self.state), "minutes": minutes, "probes": [], "heartbeat_ages": []}
        try:
            self.start()
            started = time.time()
            while time.time() - started < minutes * 60:
                question = self.say(CONFIDENT, mention=True)
                answer = self.wait_for("the probe's answer", lambda: self.sent_answer(question), REPLY_TIMEOUT + 10)
                replies = self.rows("SELECT COUNT(*) AS n FROM outbox WHERE reply_to=? AND status='sent'", (question,))[0]["n"]
                assert replies == 1, f"A probe got {replies} answers"
                report["probes"].append({"question": question, "answer": answer["message_id"]})
                until = min(started + minutes * 60, time.time() + SOAK_PROBE_SECONDS)
                while time.time() < until:
                    time.sleep(min(30, max(1, until - time.time())))
                    beat = self.store.get_meta("heartbeat", {}).get("at")
                    if beat:
                        report["heartbeat_ages"].append(round(time.time() - datetime.fromisoformat(beat).timestamp(), 1))
            oldest = max(report["heartbeat_ages"], default=0)
            assert oldest <= HEARTBEAT_LIMIT, f"The heartbeat went silent for {oldest}s"
            assert self.rows("SELECT 1 FROM outbox WHERE status IN ('retry', 'failed', 'refused', 'gone')") == []
            report["ok"] = True
            report["state_mb"] = round(sum(path.stat().st_size for path in self.state.glob("assistant.sqlite*")) / 1e6, 2)
        except (E2EError, AssertionError) as exc:
            report["ok"] = False
            report["error"] = str(exc)
        finally:
            self.stop()
        return report

    # ---- plumbing ----

    def _reset(self) -> None:
        shutil.rmtree(self.state, ignore_errors=True)
        write_local_config(self.state, chat_whitelist=[LIVE_CHAT], working_hours={"start": 0, "end": 24}, working_days=list(range(7)))
        self.config = AssistantConfig.load(self.root, self.state)
        self.store = Store(self.state / "assistant.sqlite")
        self.index, _ = ensure_index(self.root, self.config, self.state, created_at=iso(time.time()))
        self.engine = Engine(self.store, self.index, self.config, self.root, self.state)
        Policy(explicit=True, proactive="observe").save(self.store)
        self.bot_id = lark.bot(self.config)["open_id"]

    def step(self, name: str, run: Callable[[], Any]) -> Any:
        started = time.time()
        detail = run()
        self.steps.append({"step": name, "ok": True, "seconds": round(time.time() - started, 1), "detail": detail})
        return detail

    def rows(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        return self.store.fetchall(sql, params)

    def one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        return self.store.fetchone(sql, params)

    def user(self, *args: str) -> dict[str, Any]:
        """One lark-cli call as the user. Only this class does that, and only against the test group."""

        completed = subprocess.run([self.config.lark_cli, *args, "--as", "user"], capture_output=True, text=True)
        try:
            envelope = json.loads(completed.stdout or completed.stderr)
        except ValueError:
            envelope = {}
        if completed.returncode != 0 or not envelope.get("ok", False):
            error = envelope.get("error") or {}
            raise E2EError(f"lark-cli as the user failed: {error.get('message') or completed.stderr.strip()[:300]}")
        return envelope.get("data") or {}

    def say(self, text: str, *, reply_to: str = "", mention: bool = False) -> str:
        key = f"e2e-{int(time.time() * 1000)}-{len(self.steps)}"
        content = json.dumps({"text": f'<at user_id="{self.bot_id}"></at> {text}' if mention else text}, ensure_ascii=False)
        if reply_to:
            args = ["im", "+messages-reply", "--message-id", reply_to, "--reply-in-thread"]
        else:
            args = ["im", "+messages-send", "--chat-id", LIVE_CHAT]
        return str(self.user(*args, "--msg-type", "text", "--content", content, "--idempotency-key", key)["message_id"])

    def react(self, message_id: str, emoji: str) -> None:
        body = json.dumps({"reaction_type": {"emoji_type": emoji}})
        self.user("im", "reactions", "create", "--message-id", message_id, "--data", body)

    def wait_for(self, what: str, condition: Callable[[], Any], timeout: float) -> Any:
        deadline = time.time() + timeout
        while time.time() < deadline:
            found = condition()
            if found:
                return found
            time.sleep(0.5)
        raise E2EError(f"Nothing came within {timeout:g}s: {what}")

    def start(self) -> None:
        """The resident process as a child, exactly as a session would start it."""

        command = [sys.executable, str(self.root / "briefing.py"), "assistant", "--state-dir", str(self.state), "serve"]
        self.process = subprocess.Popen(command, cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pid = self.process.pid

        def ready() -> bool:
            service = self.store.get_meta("service", {})
            consumers = service.get("consumers") or {}
            return service.get("pid") == pid and bool(consumers) and all(item.get("state") == "ready" for item in consumers.values())

        try:
            self.wait_for("the resident process and its consumers to be ready", ready, READY_TIMEOUT)
        except E2EError as exc:
            raise E2EError(f"{exc}; the process reported: {self.store.get_meta('service', {}).get('error')}") from None

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            (self.state / "stop").write_text("stop", encoding="utf-8")
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=10)
        self.process = None

    def crash(self) -> None:
        """Kill the process the hard way; its consumers exit on their own when stdin closes."""

        assert self.process is not None
        self.process.kill()
        self.process.wait(timeout=10)
        self.process = None

    def thread(self, root_message_id: str) -> list[dict[str, Any]]:
        """The messages of the thread a root message opened, oldest first."""

        page = lark.records(self.config, container_type="chat", container_id=LIVE_CHAT, start_ms=int((time.time() - 900) * 1000))
        thread_id = next((item.get("thread_id") for item in page if item["message_id"] == root_message_id), None)
        return lark.records(self.config, container_type="thread", container_id=thread_id, start_ms=0) if thread_id else []

    def sent_answer(self, reply_to: str) -> dict[str, Any] | None:
        return self.one("SELECT * FROM outbox WHERE reply_to=? AND status='sent'", (reply_to,))

    @staticmethod
    def _task_input(task: dict[str, Any]) -> dict[str, Any]:
        return read_json(Path(task["input_path"]), {})

    def _verdict(self, task: dict[str, Any]) -> dict[str, Any]:
        """What a host session would write for an assessment: the first rule matches and quotes the last message."""

        payload = self._task_input(task)
        quote = next((message["text"][:6] for message in reversed(payload["messages"]) if len(message["text"]) >= 6), "")
        return {
            "schema_version": 1, "_task": {"task_id": task["task_id"], "kind": "assess"},
            "rules": [
                {"rule_id": rule["id"], "matches": index == 0, "evidence_quote": quote if index == 0 else "", "reason": "E2E stand-in session"}
                for index, rule in enumerate(payload["rules"])
            ],
            "doc_id": payload["candidates"][0]["id"] if payload["candidates"] else None,
            "relevance": "high",
        }

    # ---- the scenarios ----

    def s0_site(self) -> dict[str, Any]:
        status = urllib.request.urlopen(self.config.site_base_url, timeout=15).status
        assert status == 200, f"The published site answered {status}"
        return {"status": status}

    def s1_mention(self) -> dict[str, Any]:
        question = self.say(CONFIDENT, mention=True)
        answer = self.wait_for("the answer", lambda: self.sent_answer(question), REPLY_TIMEOUT)
        event = self.one("SELECT created_ms FROM events WHERE message_id=?", (question,))
        assert event is not None
        seconds = datetime.fromisoformat(answer["sent_at"]).timestamp() - event["created_ms"] / 1000

        placed = [item for item in self.thread(question) if item["message_id"] == answer["message_id"]]
        assert placed and placed[0]["root_id"] == question, "The answer is not inside the question's thread"
        assert self.rows("SELECT COUNT(*) AS n FROM outbox WHERE reply_to=?", (question,)) == [{"n": 1}], "A mention got more than one reply"

        links = URL.findall(answer["text"])
        assert links and all(link.startswith(self.config.site_base_url) for link in links), answer["text"]
        ids = [match.group(1) for match in LINK_ID.finditer(" ".join(links))]
        assert all(any(doc["id"].endswith(doc_id) for doc in self.index.docs) for doc_id in ids), ids
        return {"question": question, "answer": answer["message_id"], "seconds": round(seconds, 1), "links": len(links)}

    def s2_crash_restart(self, question: str) -> dict[str, Any]:
        before = self.rows("SELECT kind, COUNT(*) AS n FROM outbox WHERE status='sent' GROUP BY kind")
        self.crash()
        self.start()
        time.sleep(REPLY_TIMEOUT)
        after = self.rows("SELECT kind, COUNT(*) AS n FROM outbox WHERE status='sent' GROUP BY kind")
        assert after == before, f"Sending changed after a restart: {before} -> {after}"
        return {"sent": after}

    def s3_thread(self, question: str) -> dict[str, Any]:
        follow_up = self.say(CONFIDENT, reply_to=question, mention=True)
        answer = self.wait_for("the answer inside the thread", lambda: self.sent_answer(follow_up), REPLY_TIMEOUT)
        placed = [item for item in self.thread(question) if item["message_id"] == answer["message_id"]]
        assert placed and placed[0]["root_id"] == question, "The answer left the thread"
        return {"answer": answer["message_id"]}

    def s4_refine(self) -> dict[str, Any]:
        question = self.say(UNSURE, mention=True)
        task = self.wait_for(
            "a refinement task", lambda: self.one("SELECT * FROM tasks WHERE trigger_id=? AND status='pending'", (f"feishu:{question}",)), REPLY_TIMEOUT
        )
        assert self.rows("SELECT 1 FROM outbox WHERE reply_to=?", (question,)) == [], "Something was said before the answer was ready"
        payload = self._task_input(task)
        chosen = payload["candidates"][0]["id"]
        output = {
            "schema_version": 1, "_task": {"task_id": task["task_id"], "kind": "refine"}, "queries": ["分层卸载"],
            "selected": [{"doc_id": chosen, "quote": payload["question"][:6]}], "none_relevant": False,
        }
        result = self.engine.apply_task(task["task_id"], output)
        assert result["ok"], result
        answer = self.wait_for("the refined answer", lambda: self.sent_answer(question), REPLY_TIMEOUT + 5)
        assert answer["text"].startswith("日报库里相关的：") and within_limit(answer["text"])
        return {"question": question, "answer": answer["message_id"]}

    def s5_card_observe(self) -> str:
        ideas = load_ideas(self.root)
        idea = max(ideas.values(), key=lambda item: (len(item.get("evidence_for") or []), item["idea_id"]))
        now = time.time()
        key = f"card:e2e:{idea['idea_id']}"
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO registry(message_id, idea_id, issue_date, pushed_at) VALUES(?, ?, 'e2e', ?)",
                (outbox.PENDING_CARD + key, idea["idea_id"], iso(now)),
            )
            outbox.enqueue(
                self.store, connection, key=key, kind="card", chat_id=LIVE_CHAT, reply_to="",
                text=card_json(card(idea, stored_copy(idea), self.config.site_base_url)), thread_key=None, now=now,
            )
        assert outbox.flush(self.store, lark.LarkTransport(self.config), now)["sent"] == 1
        card_message = self.one("SELECT message_id FROM registry WHERE idea_id=?", (idea["idea_id"],))["message_id"]

        self.say(UNDER_CARD, reply_to=card_message)
        task = self.wait_for(
            "the discussion under the card to be assessed", lambda: self.one("SELECT * FROM tasks WHERE kind='assess' AND status='pending'"), QUIET_TIMEOUT
        )
        payload = self._task_input(task)
        assert payload["anchored_idea"]["id"] == f"idea:{idea['idea_id']}", payload.get("anchored_idea")
        assert [message["sender"] for message in payload["messages"]] == ["同事 A"], payload["messages"]
        assert self.engine.apply_task(task["task_id"], self._verdict(task))["outcome"] == "observe_would_accept"
        assert self.rows("SELECT 1 FROM outbox WHERE kind='recommendation'") == [], "Observe mode said something"
        assert self.rows("SELECT mode, outcome FROM decisions WHERE kind='assess'") == [{"mode": "observe", "outcome": "observe_would_accept"}]
        return card_message

    def s6_auto_dislike(self, card_message: str) -> dict[str, Any]:
        policy = Policy.load(self.store)
        policy.proactive = "auto"
        policy.save(self.store)

        self.say(AGAIN, reply_to=card_message)
        task = self.wait_for(
            "the discussion to be assessed again", lambda: self.one("SELECT * FROM tasks WHERE kind='assess' AND status='pending'"), QUIET_TIMEOUT
        )
        assert self.engine.apply_task(task["task_id"], self._verdict(task))["outcome"] == "recommended"
        recommendation = self.wait_for(
            "the recommendation", lambda: self.one("SELECT * FROM outbox WHERE kind='recommendation' AND status='sent'"), REPLY_TIMEOUT + 5
        )
        assert recommendation["text"].startswith("这个方向") and recommendation["text"].count("[查看详情](") == 1
        placed = [item for item in self.thread(card_message) if item["message_id"] == recommendation["message_id"]]
        assert placed and placed[0]["root_id"] == card_message, "The recommendation left the card's thread"

        self.react(recommendation["message_id"], "ThumbsDown")
        self.wait_for("the dislike to be recorded", lambda: self.one("SELECT 1 FROM feedback WHERE message_id=?", (recommendation["message_id"],)), REPLY_TIMEOUT + 5)
        assessed = len(self.rows("SELECT 1 FROM tasks WHERE kind='assess'"))
        self.say(AFTER_DISLIKE, reply_to=card_message)
        time.sleep(QUIET_TIMEOUT)
        assert len(self.rows("SELECT 1 FROM tasks WHERE kind='assess'")) == assessed, "The discussion was assessed again after a dislike"
        assert self.rows("SELECT reason FROM dispositions WHERE reason='thread_muted'"), "The last message was not left alone because of the dislike"
        return {"recommendation": recommendation["message_id"]}

    def s7_counts(self) -> dict[str, Any]:
        sent = {row["kind"]: row["n"] for row in self.rows("SELECT kind, COUNT(*) AS n FROM outbox WHERE status='sent' GROUP BY kind")}
        assert sent == {"answer": 3, "card": 1, "recommendation": 1}, sent
        assert self.rows("SELECT 1 FROM outbox WHERE status IN ('retry', 'failed', 'refused', 'gone')") == []
        assert [row["choice"] for row in self.rows("SELECT choice FROM feedback")] == ["down"]
        counts = {row["decision"]: row["n"] for row in self.rows("SELECT decision, COUNT(*) AS n FROM dispositions GROUP BY decision")}
        assert counts == {"answered": 3, "silent": 1, "recommended": 1, "ignored": 1}, counts
        return {"sent": sent, "dispositions": counts}
