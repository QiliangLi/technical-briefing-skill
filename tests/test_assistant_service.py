"""Tests for the resident process: events in, replies out, and its own housekeeping."""

import json
import os
from collections import deque

import pytest

from assistant_support import ALICE, BASE, BOT, CHAT, FakeTransport, World
from briefing_skill.assistant import lark
from briefing_skill.assistant import service as service_module
from briefing_skill.assistant.constants import INDEX_RETRY_SECONDS, TICK_FAILURE_LIMIT
from briefing_skill.assistant.retrieval import LexicalIndex
from briefing_skill.assistant.service import AlreadyRunning, Service, overview, request_stop, self_check
from briefing_skill.assistant.timeutil import iso
from briefing_skill.utils import write_json

CONFIDENT = "KV cache 分层卸载怎么做"
OTHER = "oc_" + "9" * 32


class FakeConsumer:
    """Every consumer of one EventKey reads the same queue, like a restarted child would."""

    def __init__(self, event_key: str, queue: deque[dict]) -> None:
        self.event_key = event_key
        self.queue = queue
        self.ready = True
        self.code: int | None = None
        self.error: dict = {}
        self.stopped = False

    def start(self) -> None:
        return None

    def wait_ready(self, timeout: float) -> bool:
        return self.ready

    def exit_code(self) -> int | None:
        return self.code

    def events(self) -> list[dict]:
        found = list(self.queue)
        self.queue.clear()
        return found

    def stop(self, grace: float = 10) -> None:
        self.stopped = True


class FakeClient:
    """Stands in for lark-cli: consumers to push events into and history pages to serve."""

    def __init__(self, transport: FakeTransport) -> None:
        self.sender = transport
        self.history: dict[tuple[str, str], list[dict]] = {}
        self.thread_polls: list[str] = []
        self.created = {key: [] for key in lark.EVENT_KEYS}
        self.queues: dict[str, deque[dict]] = {key: deque() for key in lark.EVENT_KEYS}
        self.buses_stopped = 0

    def bot(self) -> dict[str, str]:
        return {"open_id": BOT, "app_name": "助手"}

    def members(self, chat_id: str) -> dict[str, str]:
        return {ALICE: "张三"}

    def transport(self) -> FakeTransport:
        return self.sender

    def consumer(self, event_key: str) -> FakeConsumer:
        self.created[event_key].append(FakeConsumer(event_key, self.queues[event_key]))
        return self.created[event_key][-1]

    def records(self, *, container_type: str, container_id: str, start_ms: int) -> list[dict]:
        if container_type == "thread":
            self.thread_polls.append(container_id)
        page = self.history.get((container_type, container_id), [])
        return [item for item in page if int(item["create_time"]) >= start_ms]

    def stop_bus(self) -> None:
        self.buses_stopped += 1

    def push(self, event_key: str, event: dict) -> None:
        self.queues[event_key].append(event)


def _item(item_id: str, title: str, conclusion: str) -> dict:
    return {"brief_item_id": item_id, "title": title, "core_conclusion": conclusion, "keywords": []}


def message_event(message_id, created_ms, text, *, sender=ALICE, mention=False, chat=CHAT, chat_type="group"):
    mentions = [{"id": BOT, "name": "助手"}] if mention else []
    return {
        "type": lark.MESSAGE_EVENT, "message_id": message_id, "chat_id": chat, "chat_type": chat_type, "sender_id": sender,
        "sender_type": "user", "create_time": str(created_ms), "root_id": "",
        "content": ("@助手 " if mention else "") + text, "mentions": mentions,
    }


def record(message_id, create_time, text, *, root="", thread_id="", mention=False):
    return {
        "message_id": message_id, "chat_id": CHAT, "chat_type": "group", "msg_type": "text", "create_time": str(create_time),
        "body": {"content": json.dumps({"text": ("@_user_1 " if mention else "") + text}, ensure_ascii=False)},
        "sender": {"id": ALICE, "sender_type": "user"}, "root_id": root, "thread_id": thread_id,
        "mentions": [{"id": BOT, "key": "@_user_1"}] if mention else [],
    }


@pytest.fixture
def world(tmp_path):
    world = World(tmp_path)
    world.client = FakeClient(world.transport)
    world.service = Service(world.root, world.config, world.state, client=world.client, store=world.store, clock=lambda: world.now)
    return world


def run(world, ticks: int) -> int:
    """Run the resident process for a number of one-second ticks, then stop it."""

    left = [ticks]

    def sleep(seconds: float) -> None:
        world.advance(seconds)
        left[0] -= 1
        if left[0] <= 0:
            world.service.stop_path.write_text("stop", encoding="utf-8")

    world.service.sleep = sleep
    return world.service.run()


# ---- events in, replies out ----


def test_a_live_mention_is_answered_in_its_thread(world):
    world.client.push(lark.MESSAGE_EVENT, message_event("om_live", int(BASE * 1000), CONFIDENT, mention=True))
    assert run(world, 6) == 0
    assert world.transport.sent[0]["reply_to"] == "om_live"
    assert world.transport.sent[0]["text"].startswith("日报库里相关的：")
    assert world.store.fetchone("SELECT first_via FROM events")["first_via"] == "event"


def test_the_bots_own_messages_are_dropped(world):
    world.client.push(lark.MESSAGE_EVENT, message_event("om_own", int(BASE * 1000), CONFIDENT, sender=BOT, mention=True))
    assert run(world, 2) == 0
    assert world.store.fetchall("SELECT * FROM dispositions") == [] and world.transport.calls == 0


def test_a_direct_message_is_answered_only_for_a_member(world):
    run(world, 1)
    assert world.store.get_meta("members") == {CHAT: [ALICE]}
    moment = int(world.now * 1000)
    world.client.push(lark.MESSAGE_EVENT, message_event("om_dm", moment, CONFIDENT, chat=OTHER, chat_type="p2p"))
    world.client.push(
        lark.MESSAGE_EVENT, message_event("om_stranger", moment, CONFIDENT, sender="ou_stranger", chat=OTHER, chat_type="p2p")
    )
    run(world, 7)  # long enough for the next sweep to send
    assert [row["reason"] for row in world.store.fetchall("SELECT reason FROM dispositions ORDER BY rowid")] == [
        "confident", "direct_non_member"
    ]
    assert world.transport.sent[-1]["chat_id"] == OTHER


def test_backfill_recovers_a_missed_message_and_the_replies_inside_its_thread(world):
    run(world, 1)  # the first round only sets the cursor
    world.advance(30)
    moment = int(world.now * 1000)
    world.client.history[("chat", CHAT)] = [record("om_missed", moment, CONFIDENT, thread_id="omt_1", mention=True)]
    world.client.history[("thread", "omt_1")] = [record("om_reply", moment + 1000, "话题里的回复", root="om_missed")]
    assert run(world, 95) == 0  # rounds at +60 s and +120 s; the third round polls threads

    first_via = {row["message_id"]: row["first_via"] for row in world.store.fetchall("SELECT message_id, first_via FROM events")}
    assert first_via == {"om_missed": "backfill", "om_reply": "thread"}
    assert set(world.client.thread_polls) == {"omt_1"}
    thread = world.store.fetchone("SELECT * FROM threads WHERE root_message_id='om_missed'")
    assert (thread["thread_id"], thread["last_activity_ms"]) == ("omt_1", moment + 1000)  # the reply is the latest activity
    assert len(world.transport.sent) == 1 and world.transport.sent[0]["reply_to"] == "om_missed"


def test_reaction_and_card_events_reach_the_ledger(world):
    world.store.execute(
        "INSERT INTO registry(message_id, idea_id, issue_date, pushed_at) VALUES('om_card', 'idea_c', '2026-10-01', '2026-10-06T10:00:00')"
    )
    world.client.push(
        lark.REACTION_EVENTS[0],
        {
            "header": {"event_type": lark.REACTION_EVENTS[0]},
            "event": {"message_id": "om_card", "reaction_type": {"emoji_type": "ThumbsDown"}, "user_id": {"open_id": ALICE}},
        },
    )
    world.client.push(
        lark.CARD_EVENT,
        {
            "type": lark.CARD_EVENT, "action_tag": "button", "action_value": json.dumps({"choice": "worth_testing", "idea": "idea_c"}),
            "message_id": "om_card", "chat_id": CHAT, "operator_id": ALICE,
        },
    )
    assert run(world, 1) == 0
    assert world.store.fetchall("SELECT source, choice, idea_id, operator_id FROM feedback ORDER BY source") == [
        {"source": "button", "choice": "worth_testing", "idea_id": "idea_c", "operator_id": ALICE},
        {"source": "reaction", "choice": "not_promising", "idea_id": "idea_c", "operator_id": ALICE},
    ]


# ---- supervision ----


def test_a_crashed_consumer_is_restarted_with_backoff_and_an_auth_error_is_kept(world):
    service, key = world.service, lark.MESSAGE_EVENT
    service._open()
    try:
        world.client.created[key][-1].code = 0
        service._supervise(world.now)
        assert service.consumer_state[key] == {"state": "restarting", "why": "exited with code 0", "in_seconds": 1.0}
        service._supervise(world.now)
        assert len(world.client.created[key]) == 1

        world.advance(1)
        service._supervise(world.now)
        assert len(world.client.created[key]) == 2
        world.advance(61)
        service._supervise(world.now)

        world.client.created[key][-1].code = 0
        service._supervise(world.now)
        assert service.consumer_state[key]["in_seconds"] == 1.0  # a minute of clean running resets the wait
        world.advance(1)
        service._supervise(world.now)
        world.client.created[key][-1].code = 0
        service._supervise(world.now)
        assert service.consumer_state[key]["in_seconds"] == 2.0  # then it doubles
        world.advance(2)
        service._supervise(world.now)

        world.client.created[key][-1].code, world.client.created[key][-1].error = 2, {"type": "missing_scope"}
        service._supervise(world.now)
        assert service.consumer_state[key] == {"state": "error", "error": {"type": "missing_scope"}}
        world.advance(600)
        service._supervise(world.now)
        assert len(world.client.created[key]) == 4
    finally:
        service._shutdown()


def test_a_consumer_that_cannot_start_is_reported_and_the_others_keep_running(world):
    service = world.service
    start = world.client.consumer

    def consumer(event_key: str) -> FakeConsumer:
        if event_key == lark.CARD_EVENT:
            raise OSError("cannot spawn")
        return start(event_key)

    world.client.consumer = consumer
    service._open()
    try:
        assert service.consumer_state[lark.CARD_EVENT] == {"state": "error", "error": {"message": "cannot spawn"}}
        assert service.consumers[lark.CARD_EVENT] is None
        assert all(consumer is not None for event_key, consumer in service.consumers.items() if event_key != lark.CARD_EVENT)
    finally:
        service._shutdown()


# ---- lifecycle ----


def test_stopping_closes_every_consumer_and_the_bus(world):
    assert run(world, 3) == 0
    assert all(consumer.stopped for consumers in world.client.created.values() for consumer in consumers)
    assert world.client.buses_stopped == 1
    assert not world.service.pid_path.exists() and not world.service.stop_path.exists()
    service = world.store.get_meta("service")
    assert service["pid"] is None and service["stopped_at"] == iso(world.now)
    assert {state["state"] for state in service["consumers"].values()} == {"ready"}


def test_a_second_process_over_a_live_one_refuses_to_start(world):
    world.service.pid_path.write_text(f"{os.getppid()}\n", encoding="utf-8")  # a live process that is not this one

    def must_not_run(seconds: float) -> None:
        raise AssertionError("a second resident process must never reach its loop")

    world.service.sleep = must_not_run
    with pytest.raises(AlreadyRunning, match="already running"):
        world.service.run()
    assert world.client.buses_stopped == 0 and world.service.pid_path.exists()


def test_stop_without_a_running_process_only_cleans_up(world):
    world.service.pid_path.write_text("999999999\n", encoding="utf-8")
    assert request_stop(world.state, timeout=0) == {"running": False, "stopped": True}
    assert not world.service.pid_path.exists()


HALF_WRITTEN = "Expecting value: line 1 column 1 (char 0)"  # what a file looks like while a briefing run writes it


def test_a_tick_that_reads_a_half_written_corpus_is_ridden_out(world, monkeypatch):
    original = service_module.Engine.sweep
    failures = []

    def flaky(self) -> dict:
        failures.append(1)
        if len(failures) == 1:
            raise ValueError(HALF_WRITTEN)
        return original(self)

    monkeypatch.setattr(service_module.Engine, "sweep", flaky)
    assert run(world, 8) == 0
    assert len(failures) >= 2 and world.store.get_meta("service")["tick_error"] is None


def test_a_minute_of_failing_ticks_stops_the_process_with_the_reason(world, monkeypatch):
    def broken(self) -> dict:
        raise RuntimeError("ledger is locked")

    monkeypatch.setattr(service_module.Engine, "sweep", broken)
    assert run(world, TICK_FAILURE_LIMIT * 3) == 1
    service = world.store.get_meta("service")
    assert service["error"] == "RuntimeError: ledger is locked"
    assert (service["tick_error"]["count"], service["tick_error"]["message"]) == (TICK_FAILURE_LIMIT, "RuntimeError: ledger is locked")


def test_startup_waits_out_a_corpus_being_rewritten(world, monkeypatch):
    attempts = []
    real = service_module.ensure_index

    def being_rewritten(root, config, state_dir, created_at=None):
        attempts.append(1)
        if len(attempts) <= 2:
            raise ValueError(HALF_WRITTEN)
        return real(root, config, state_dir, created_at=created_at)

    monkeypatch.setattr(service_module, "ensure_index", being_rewritten)
    world.service.sleep = world.advance
    started = world.now
    world.service._open()
    try:
        assert len(attempts) == 3 and world.now - started == 2 * INDEX_RETRY_SECONDS
    finally:
        world.service._shutdown()


def test_a_stale_index_is_rebuilt_at_the_hourly_check(world):
    service = world.service
    service._open()
    try:
        issue = world.root / "archive" / "issues" / "2026-10-01" / "issue.json"
        data = json.loads(issue.read_text(encoding="utf-8"))
        data["items"][0]["title"] = "改过的标题"
        issue.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        service._refresh_index(world.now)
        assert service.engine.index.get("item:" + "a" * 24)["title"] == "改过的标题"
        assert world.store.get_meta("index")["documents"] == world.index.n
    finally:
        service._shutdown()


# ---- status and the self-check ----


def test_ops_01_the_self_check_reports_an_index_that_no_longer_answers(world):
    good = self_check(world.root, world.config, world.state, world.index, world.now)
    assert good == {"ok": True, "problems": [], "documents": world.index.n, "probe_state": "confident", "checked_at": iso(world.now)}

    unrelated = LexicalIndex.build(
        [{"id": "item:x", "kind": "item", "title": "无关条目", "search": "无关条目", "url": "https://example.test/x"}], "digest"
    )
    probe = self_check(world.root, world.config, world.state, unrelated, world.now)
    assert probe["problems"] == ["The fixed probe question is no longer answered with confidence (state: none)"]
    assert self_check(world.root, world.config, world.state, None, world.now)["problems"] == ["The index is empty"]

    for snapshot in (world.state / "index").glob("*.json"):
        snapshot.unlink()
    stale = self_check(world.root, world.config, world.state, world.index, world.now)
    assert stale["problems"] == [
        "The index snapshot no longer matches the published corpus; run `python briefing.py assistant index build`"
    ]


def test_status_reads_the_ledger_without_touching_the_process(world):
    service = world.service
    service._open()
    try:
        world.client.push(lark.MESSAGE_EVENT, message_event("om_live", int(world.now * 1000), CONFIDENT, mention=True))
        service._tick()
        report = overview(world.store, world.root, world.config, world.state, world.now)
    finally:
        service._shutdown()

    assert report["service"]["running"] and report["service"]["pid"] == os.getpid()
    assert {key: state["state"] for key, state in report["service"]["consumers"].items()} == dict.fromkeys(lark.EVENT_KEYS, "ready")
    assert report["service"]["heartbeat_age_seconds"] == 0
    assert report["policy"] == {"explicit": True, "proactive": "auto", "muted_for_seconds": 0, "report_to": None}
    assert report["today"] == {"dispositions": {"answered": 1}, "sent": {"answer": 1}, "decisions": {"answer:answered": 1}}
    assert report["outbox"] == {"sent": 1} and report["tasks"] == {"wakes": 0} and report["reports"] == {}
    assert report["self_check"]["ok"] and report["index"]["documents"] == world.index.n


def test_a_new_issue_is_offered_to_the_group_once_and_only_when_it_is_new(world):
    def publish(date: str) -> None:
        index_path = world.root / "archive" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["issues"].append({"date": date, "papers_file": f"issues/{date}/papers.json"})
        write_json(index_path, index)
        write_json(world.root / "archive" / "issues" / date / "issue.json", {"items": [_item("c" * 24, "新一期的一条", "新一期的结论。")]})
        write_json(world.root / "archive" / "issues" / date / "reader.json", {"headline": "新一期", "items": {}, "judgements": []})

    service = world.service
    service._open()
    try:
        assert world.tasks(kind="alert") == []  # the first start is not news
        service._refresh_index(world.now)
        assert world.tasks(kind="alert") == []

        publish("2026-10-20")
        service._refresh_index(world.now)
        assert [task["thread_key"] for task in world.tasks(kind="alert")] == ["alert:2026-10-20"]
        service._refresh_index(world.now + 3600)
        assert len(world.tasks(kind="alert")) == 1
        assert world.store.get_meta("index")["head_issue"] == "2026-10-20"
    finally:
        service._shutdown()
