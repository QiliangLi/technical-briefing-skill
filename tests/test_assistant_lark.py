"""Tests for the lark-cli wrapper, transport, readers and consumer (SEC-01 and the wire contract)."""

import json
import subprocess
import sys
import textwrap
import time

import pytest

from briefing_skill.assistant import lark
from briefing_skill.assistant.config import AssistantConfig
from briefing_skill.assistant.outbox import SendResult

CHAT = "oc_" + "1" * 32
CONFIG = AssistantConfig(lark_cli="lark-cli")

STREAMING = """
import json, sys
key = sys.argv[3]
print(f"[event] ready event_key={key}", file=sys.stderr, flush=True)
print(json.dumps({"type": key, "message_id": "om_1"}), flush=True)
print("not json", flush=True)
sys.stdin.readline()
print("reason: signal", file=sys.stderr)
"""
STUBBORN = """
import signal, sys, time
print(f"[event] ready event_key={sys.argv[3]}", file=sys.stderr, flush=True)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
time.sleep(60)
"""
FAILING = """
import json, sys
print(json.dumps({"ok": False, "error": {"type": "missing_scope", "missing_scopes": ["im:message"]}}), file=sys.stderr, flush=True)
sys.exit(2)
"""


def completed(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout, stderr)


def canned(monkeypatch, replies):
    """Replace the subprocess call with canned envelopes; returns the calls made."""

    calls = []

    def run(command, **options):
        calls.append({"command": command, **options})
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(lark.subprocess, "run", run)
    return calls


def until(condition, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("condition was not met in time")


@pytest.fixture
def fake_cli(tmp_path):
    """Write a stand-in for lark-cli and return a config that points at it."""

    def write(body: str) -> AssistantConfig:
        path = tmp_path / "fake-lark"
        path.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body).lstrip(), encoding="utf-8")
        path.chmod(0o755)
        return AssistantConfig(lark_cli=str(path))

    return write


# ---- the wrapper ----


def test_sec_01_the_wrapper_refuses_every_identity_but_the_bot():
    with pytest.raises(lark.LarkError, match="fixed to the bot"):
        lark.run(CONFIG, "im", "+messages-send", "--as", "user", "--text", "x")
    with pytest.raises(lark.LarkError, match="fixed to the bot"):
        lark.run(CONFIG, "api", "GET", "/open-apis/im/v1/messages", "--as=auto")


def test_stopping_the_local_bus_is_the_one_command_without_an_identity(monkeypatch):
    calls = canned(monkeypatch, [completed(json.dumps({"ok": True, "data": {}}))])
    lark.run(CONFIG, "event", "stop")
    assert calls[0]["command"] == ["lark-cli", "event", "stop"]
    with pytest.raises(lark.LarkError, match="fixed to the bot"):
        lark.run(CONFIG, "event", "stop", "--as", "user")


def test_every_command_runs_as_the_bot_and_returns_its_envelope(monkeypatch):
    calls = canned(monkeypatch, [completed(json.dumps({"ok": True, "data": {"message_id": "om_1"}}))])
    envelope = lark.run(CONFIG, "im", "+messages-reply", "--message-id", "om_0", "--markdown", "-", stdin="hi")
    assert calls[0]["command"] == ["lark-cli", "im", "+messages-reply", "--message-id", "om_0", "--markdown", "-", "--as", "bot"]
    assert calls[0]["input"] == "hi" and calls[0]["text"] is True
    assert envelope["data"]["message_id"] == "om_1"


def test_a_failure_raises_with_its_envelope_and_a_hang_raises_too(monkeypatch):
    error = {"type": "api", "code": 99992354, "message": "The request you send is not a valid {open_message_id} or not exists"}
    canned(monkeypatch, [completed(stderr=json.dumps({"ok": False, "error": error}), code=1), subprocess.TimeoutExpired("lark-cli", 30)])
    with pytest.raises(lark.LarkError, match="not exists") as caught:
        lark.run(CONFIG, "im", "+messages-reply", "--message-id", "om_x")
    assert caught.value.error["code"] == 99992354 and lark.undeliverable(caught.value)
    with pytest.raises(lark.LarkError, match="timed out"):
        lark.run(CONFIG, "im", "+messages-reply", "--message-id", "om_x")


def test_the_wire_key_fits_the_limit_and_never_collides_on_a_prefix():
    long_id = f"recommendation:{CHAT}:om_{'a' * 26}:1791252395"
    key = lark.wire_key(long_id)
    assert len(key) <= 50 and key == lark.wire_key(long_id)
    assert len({lark.wire_key(long_id + str(digit)) for digit in range(10)}) == 10


# ---- the transport ----


@pytest.mark.parametrize(
    "reply_to, kind, command",
    [
        ("om_1", "answer", ["im", "+messages-reply", "--message-id", "om_1", "--markdown", "-", "--reply-in-thread"]),
        ("", "answer", ["im", "+messages-send", "--chat-id", CHAT, "--markdown", "-"]),
        ("", "card", ["im", "+messages-send", "--chat-id", CHAT, "--msg-type", "interactive", "--content", "-"]),
    ],
    ids=["reply in thread", "new message", "card"],
)
def test_the_transport_picks_the_command_from_the_message(monkeypatch, reply_to, kind, command):
    calls = canned(monkeypatch, [completed(json.dumps({"ok": True, "data": {"message_id": "om_9"}}))])
    result = lark.LarkTransport(CONFIG).send(CHAT, reply_to, "**正文**", "answer:feishu:om_1", kind)
    assert result == SendResult("sent", message_id="om_9")
    assert calls[0]["command"][1:] == [*command, "--idempotency-key", lark.wire_key("answer:feishu:om_1"), "--as", "bot"]
    assert calls[0]["input"] == "**正文**"


def test_the_transport_retries_unless_the_destination_is_gone(monkeypatch):
    def failure(code, message):
        return completed(stderr=json.dumps({"ok": False, "error": {"type": "api", "code": code, "message": message}}), code=1)

    canned(monkeypatch, [failure(99992354, "not a valid open_message_id or not exists"), failure(99991400, "too many requests")])
    transport = lark.LarkTransport(CONFIG)
    gone = transport.send(CHAT, "om_1", "x", "a", "answer")
    retry = transport.send(CHAT, "om_1", "x", "b", "answer")
    assert (gone.status, retry.status) == ("gone", "retry")
    assert "not exists" in gone.error and "too many requests" in retry.error


# ---- readers ----


def _record(message_id, create_time, *, root="", thread_id="", text="消息"):
    return {
        "message_id": message_id, "chat_id": CHAT, "chat_type": "group", "msg_type": "text", "create_time": str(create_time),
        "body": {"content": json.dumps({"text": text})}, "sender": {"id": "ou_alice", "sender_type": "user"},
        "root_id": root, "thread_id": thread_id,
    }


def test_history_reads_newest_first_back_to_the_cursor_and_a_thread_in_its_own_container(monkeypatch):
    pages = [
        {"ok": True, "data": {"items": [_record("om_2", 2000), _record("om_1", 1000, thread_id="omt_1")], "has_more": True, "page_token": "p2"}},
        {"ok": True, "data": {"items": [_record("om_3", 3000), _record("om_0", 200)], "has_more": True, "page_token": "p3"}},
        {"ok": True, "data": {"items": [_record("om_4", 4000, root="om_1"), _record("om_old", 50)], "has_more": True, "page_token": "p4"}},
    ]
    calls = canned(monkeypatch, [completed(json.dumps(page)) for page in pages])
    chat = lark.records(CONFIG, container_type="chat", container_id=CHAT, start_ms=500)
    thread = lark.records(CONFIG, container_type="thread", container_id="omt_1", start_ms=500)

    params = [json.loads(call["command"][call["command"].index("--params") + 1]) for call in calls]
    assert params[0] == {"container_id_type": "chat", "container_id": CHAT, "sort_type": "ByCreateTimeDesc", "page_size": 50}
    assert params[1]["page_token"] == "p2" and len(calls) == 3  # each read stops at the page that crosses the cursor
    assert (params[2]["container_id_type"], params[2]["container_id"]) == ("thread", "omt_1")

    assert [item["message_id"] for item in chat] == ["om_1", "om_2", "om_3"]  # oldest first, nothing before the cursor
    replies = lark.to_triggers(thread, via="thread", bot_ids=set(), chat_id=CHAT)
    assert [(reply.message_id, reply.thread_key, reply.via) for reply in replies] == [("om_4", f"{CHAT}:om_1", "thread")]
    assert lark.thread_roots(chat) == [(CHAT, "om_1", "omt_1", 1000)]


def test_the_bot_identity_and_the_members_come_from_the_api(monkeypatch):
    canned(
        monkeypatch,
        [
            completed(json.dumps({"ok": True, "data": {"items": [{"member_id": "ou_a", "name": "张三"}, {"member_id": "ou_b"}], "has_more": False}})),
            completed(json.dumps({"ok": True, "data": {"open_id": "ou_bot", "app_name": "助手"}})),
        ],
    )
    assert lark.members(CONFIG, CHAT) == {"ou_a": "张三", "ou_b": ""}
    assert lark.bot(CONFIG) == {"open_id": "ou_bot", "app_name": "助手"}


# ---- the consumer ----


def test_a_consumer_reports_readiness_streams_events_and_stops_on_stdin_close(fake_cli):
    consumer = lark.Consumer(fake_cli(STREAMING), lark.MESSAGE_EVENT)
    consumer.start()
    assert consumer.wait_ready(10)
    assert consumer.exit_code() is None

    seen: list[dict] = []
    until(lambda: seen.extend(consumer.events()) or bool(seen))
    assert seen == [{"type": lark.MESSAGE_EVENT, "message_id": "om_1"}]
    assert list(consumer.events()) == []

    process = consumer.process
    consumer.stop(grace=10)
    assert consumer.process is None and process.poll() == 0
    until(lambda: "reason: signal" in consumer.log)


def test_a_consumer_that_ignores_stdin_is_signalled_after_the_grace(fake_cli):
    consumer = lark.Consumer(fake_cli(STUBBORN), lark.MESSAGE_EVENT)
    consumer.start()
    assert consumer.wait_ready(10)
    process = consumer.process
    started = time.monotonic()
    consumer.stop(grace=0.5)
    assert process.poll() == 0 and time.monotonic() - started < 10


def test_a_consumer_that_fails_keeps_its_error_envelope(fake_cli):
    consumer = lark.Consumer(fake_cli(FAILING), lark.MESSAGE_EVENT)
    consumer.start()
    until(lambda: consumer.exit_code() == 2)
    assert consumer.error == {"type": "missing_scope", "missing_scopes": ["im:message"]}
