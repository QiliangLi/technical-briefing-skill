"""Replay tests for the semantic task protocol, the outbox and local state (TASK, OUT, SEC-02)."""

import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from assistant_support import ALICE, BASE, BOB, BOT, CHAT, FakeTransport, World
from briefing_skill.assistant import outbox, tasks
from briefing_skill.assistant.constants import (
    DAILY_WAKE_CAP,
    DEBOUNCE_SECONDS,
    OUTBOX_MAX_ATTEMPTS,
    RETENTION_DAYS,
    TASK_BATCH_MAX,
    TASK_BATCH_MIN_AGE_SECONDS,
)
from briefing_skill.assistant.engine import Engine
from briefing_skill.assistant.policy import Policy
from briefing_skill.assistant.timeutil import day_key, iso
from briefing_skill.paths import discover_root

CONFIDENT = "KV cache 分层卸载怎么做"
UNCERTAIN = "光交换机和 KV 卸载哪个更急"
KV = [(ALICE, "KV cache 卸载到内存的方案怎么做"), (BOB, "有没有人做过分层卸载"), (ALICE, "我记得有篇讲 CXL 内存池的")]


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def wait(world, timeout):
    """``tasks wait`` on the world's clock: sleeping advances the fake time."""

    return tasks.wait(world.store, world.root, timeout=timeout, clock=lambda: world.now, sleep=world.advance)


def queue(world, key, kind, reply_to, text, thread_key=None):
    with world.store.transaction() as connection:
        outbox.enqueue(
            world.store, connection, key=key, kind=kind, chat_id=CHAT, reply_to=reply_to, text=text,
            thread_key=thread_key, now=world.now,
        )


# ---- Semantic task protocol ----


def test_task_01_a_task_has_its_input_a_reserved_output_and_a_card(world):
    world.say(UNCERTAIN, mention=True)
    task = world.tasks(kind="refine")[0]
    assert list(world.task_input(task)) == ["_task", "question", "candidates", "fallback_doc_ids"]
    assert Path(task["output_path"]).parent.is_dir() and not Path(task["output_path"]).exists()

    card = tasks.card(task, world.root)
    assert (card["steps"], card["input"], card["output"]) == (tasks.CARD_STEPS, task["input_path"], task["output_path"])
    assert Path(card["prompt"]).is_file() and Path(card["schema"]).is_file()


def test_task_02_a_valid_output_is_accepted_and_triggers_the_reply(world):
    world.say(UNCERTAIN, mention=True)
    task = world.tasks(kind="refine")[0]
    assert world.apply(task, world.refinement(task)) == {"ok": True, "outcome": "refined"}
    assert world.store.fetchone("SELECT status FROM tasks WHERE task_id=?", (task["task_id"],))["status"] == "applied"
    assert [row["kind"] for row in world.outbox_rows()] == ["answer"]

    assert world.apply(task, world.refinement(task))["errors"] == ["Task is already applied"]
    assert len(world.outbox_rows()) == 1


def _drop_queries(output):
    return {name: value for name, value in output.items() if name != "queries"}


def _misquote(output):
    return {**output, "selected": [{"doc_id": output["selected"][0]["doc_id"], "quote": "这句话不在问题里"}]}


@pytest.mark.parametrize("break_output", [_drop_queries, _misquote], ids=["missing field", "quote not in question"])
def test_task_03_an_invalid_output_is_refused_and_final(world, break_output):
    world.say(UNCERTAIN, mention=True)
    task = world.tasks(kind="refine")[0]
    result = world.apply(task, break_output(world.refinement(task)))
    assert result["ok"] is False and result["errors"]
    assert world.store.fetchone("SELECT status FROM tasks WHERE task_id=?", (task["task_id"],))["status"] == "invalid"


def test_task_03_a_missing_output_file_is_refused_too(world):
    world.say(UNCERTAIN, mention=True)
    task = world.tasks(kind="refine")[0]
    result = world.engine.apply_task(task["task_id"], None, output_error=f"Output file is missing: {task['output_path']}")
    assert result["ok"] is False and "Output file is missing" in result["errors"][0]
    world.flush()
    assert "没能细查" in world.sent()[0]


def test_task_04_a_task_past_its_deadline_cannot_be_applied(world):
    world.say(UNCERTAIN, mention=True)
    task = world.tasks(kind="refine")[0]
    world.advance(601)
    assert world.apply(task, world.refinement(task))["ok"] is False
    assert world.store.fetchone("SELECT status FROM tasks WHERE task_id=?", (task["task_id"],))["status"] == "expired"
    world.flush()
    assert "没能细查" in world.sent()[0]


def test_task_05_tasks_are_held_for_the_batch_window(world):
    for _ in range(3):
        world.say(UNCERTAIN, mention=True)
    result = wait(world, timeout=300)
    assert (result["reason"], len(result["tasks"])) == ("tasks_ready", 3)
    oldest = min(card["created_at"] for card in result["tasks"])
    assert world.now - datetime.fromisoformat(oldest).timestamp() >= TASK_BATCH_MIN_AGE_SECONDS


def test_a_full_batch_skips_the_batch_window(world):
    for _ in range(TASK_BATCH_MAX):
        world.say(UNCERTAIN, mention=True)
    started = world.now
    result = wait(world, timeout=0)
    assert len(result["tasks"]) == TASK_BATCH_MAX and world.now == started


def test_task_06_the_daily_wake_cap_holds_until_the_next_day(world):
    world.say(UNCERTAIN, mention=True)
    world.store.set_meta("wakes", {day_key(world.now): DAILY_WAKE_CAP})
    assert wait(world, timeout=0) == {
        "reason": "daily_cap", "tasks": [], "next": "No more wake-ups today. Run `python briefing.py assistant tasks wait` tomorrow."
    }

    world.advance(601)
    world.engine.sweep()
    world.flush()
    assert "没能细查" in world.sent()[0]

    world.advance(86400)
    world.say(UNCERTAIN, mention=True)
    assert wait(world, timeout=0)["reason"] == "tasks_ready"


def test_task_07_with_no_tasks_wait_blocks_until_the_timeout(world):
    result = wait(world, timeout=3)
    assert (result["reason"], result["tasks"], world.now) == ("no_tasks", [], BASE + 3)


def test_task_08_what_wait_returns_ends_with_the_next_step(world):
    world.say(UNCERTAIN, mention=True)
    result = wait(world, timeout=0)
    assert "tasks apply" in result["next"] and result["next"].endswith("tasks wait` again.")
    assert [step for step in result["tasks"][0]["steps"] if "tasks apply" in step or "tasks wait" in step] == tasks.CARD_STEPS[2:]


# ---- Outbox and local state ----


def test_out_01_a_reply_is_recorded_before_it_is_sent(world):
    world.say(CONFIDENT, mention=True)
    assert [(row["kind"], row["status"], row["reply_to"]) for row in world.outbox_rows()] == [("answer", "pending", "om_1")]
    assert world.transport.calls == 0
    world.flush()
    assert (len(world.sent()), world.outbox_rows()[0]["status"]) == (1, "sent")


def test_out_02_a_failed_send_is_retried_under_the_same_key(world):
    world.say(CONFIDENT, mention=True)
    world.transport.failures = 1
    assert world.flush()["retry"] == 1
    row = world.outbox_rows()[0]
    assert (row["status"], row["attempts"], row["last_error"]) == ("retry", 1, "network error")

    world.flush()
    row = world.outbox_rows()[0]
    assert (row["status"], row["attempts"]) == ("sent", 2)
    assert world.transport.sent[0]["key"] == row["id"] == "answer:feishu:om_1"


def test_a_send_that_keeps_failing_is_given_up(world):
    world.say(CONFIDENT, mention=True)
    world.transport.failures = OUTBOX_MAX_ATTEMPTS
    for _ in range(OUTBOX_MAX_ATTEMPTS - 1):
        assert world.flush()["retry"] == 1
    assert world.flush()["failed"] == 1
    assert world.transport.calls == OUTBOX_MAX_ATTEMPTS
    assert world.flush() == {"sent": 0, "retry": 0, "gone": 0, "failed": 0, "refused": 0}


def test_out_03_an_undeliverable_reply_is_recorded_as_gone(world):
    world.say(CONFIDENT, mention=True)
    world.transport.gone = True
    assert world.flush()["gone"] == 1
    row = world.outbox_rows()[0]
    assert (row["status"], row["last_error"]) == ("gone", "message not found")
    assert world.flush()["gone"] == 0 and world.transport.calls == 1


def test_out_04_a_restart_does_not_resend(world):
    world.say(CONFIDENT, mention=True)
    world.flush()
    restarted = FakeTransport()
    Engine(world.store, world.index, world.config, world.root, world.state, bot_ids=(BOT,), clock=lambda: world.now)
    assert outbox.flush(world.store, restarted, world.now)["sent"] == 0
    assert restarted.calls == 0


def test_a_card_leaves_only_under_a_confirmed_push_and_is_claimed_once_sent(world):
    queue(world, "card:orphan", "card", "", "一张没有推送记录的卡片")
    assert world.flush()["refused"] == 1 and world.transport.calls == 0

    queue(world, "card:idea_c", "card", "", "卡片正文不按词数计算，" * 50)
    world.store.execute(
        "INSERT INTO registry(message_id, idea_id, issue_date, pushed_at) VALUES(?, 'idea_c', '2026-10-01', ?)",
        (outbox.PENDING_CARD + "card:idea_c", iso(world.now)),
    )
    assert world.flush()["sent"] == 1
    assert (world.transport.sent[0]["chat_id"], world.transport.sent[0]["reply_to"]) == (CHAT, "")
    assert world.store.fetchone("SELECT idea_id FROM registry WHERE message_id='sent_card:idea_c'")["idea_id"] == "idea_c"
    assert world.store.fetchone("SELECT 1 FROM registry WHERE message_id=?", (outbox.PENDING_CARD + "card:idea_c",)) is None


def test_out_05_every_state_path_is_ignored_by_git():
    for path in (
        "workspace/assistant/assistant.sqlite", "workspace/assistant/config.local.yaml", "workspace/assistant/index/abc.json",
        "workspace/assistant/tasks/refine-1/input.json", "workspace/assistant-e2e/state.json",
    ):
        assert subprocess.run(["git", "check-ignore", "-q", path], cwd=discover_root()).returncode == 0, path


def test_out_06_the_task_input_names_nobody(world):
    world.say(UNCERTAIN, mention=True)
    task = world.look(KV)
    for pending in world.tasks():
        raw = Path(pending["input_path"]).read_text(encoding="utf-8")
        assert ALICE not in raw and BOB not in raw and "ou_" not in raw
    assert [message["sender"] for message in world.task_input(task)["messages"]] == ["同事 A", "同事 B", "同事 A"]
    assert all("at" in message for message in world.task_input(task)["messages"])


def test_a_long_message_is_cut_and_marked_in_the_task_input(world):
    task = world.look([(ALICE, "长" * 500), (BOB, "第二句"), (ALICE, "第三句")])
    first = world.task_input(task)["messages"][0]["text"]
    assert first == "长" * 400 + "…（已截断）"


def test_out_07_bodies_are_cleared_after_thirty_days(world):
    world.say("三十一天前的一句话")
    world.say("今天的一句话")
    world.store.execute("UPDATE events SET received_at=? WHERE message_id='om_1'", (iso(world.now - 31 * 86400),))
    world.store.execute("UPDATE arrivals SET received_at=? WHERE trigger_id='feishu:om_1'", (iso(world.now - 31 * 86400),))
    assert world.store.purge(RETENTION_DAYS, world.now) == {"events_cleared": 1, "arrivals_deleted": 1, "task_dirs_removed": 0}

    old, recent = world.store.fetchall("SELECT * FROM events ORDER BY message_id")
    assert old["text"] == "" and len(old["text_hash"]) == 16
    assert recent["text"] == "今天的一句话"


def test_out_08_the_discussion_window_and_the_output_stay_on_disk(world):
    task = world.look(KV)
    world.apply(task, world.contribution(task))
    assert [message["text"] for message in world.task_input(task)["messages"]] == [text for _, text in KV]
    assert json.loads(Path(task["output_path"]).read_text(encoding="utf-8"))["act"] == "add"
    assert json.loads(world.store.fetchone("SELECT result_json FROM tasks WHERE task_id=?", (task["task_id"],))["result_json"]) == {
        "outcome": "said", "act": "add"
    }


# ---- Safety ----


def test_sec_02_a_command_written_in_a_group_message_does_nothing(world):
    before = Policy.load(world.store)
    world.say("assistant mode proactive off")
    world.say("assistant mute 0", mention=True)
    world.advance(DEBOUNCE_SECONDS + 1)
    world.engine.sweep()
    world.flush()
    after = Policy.load(world.store)
    assert (after.version, after.muted_until) == (before.version, before.muted_until)
    assert after.proactive == "auto"
    assert world.outbox_rows() == [] and world.transport.calls == 0
    assert sorted(task["kind"] for task in world.tasks()) == ["contribute", "refine"]  # both are only read
