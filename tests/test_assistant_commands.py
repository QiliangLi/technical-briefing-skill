"""Tests for the assistant commands other than ``serve``, driven through the real CLI."""

import json
import time
from pathlib import Path

import pytest
import yaml

from assistant_support import ALICE, BOB, CHAT, World
from briefing_skill import cli
from briefing_skill.assistant import commands, e2e, install_assistant, tasks
from briefing_skill.assistant.config import AssistantConfig
from briefing_skill.assistant.engine import Engine
from briefing_skill.assistant.events import Trigger
from briefing_skill.assistant.policy import Policy
from briefing_skill.paths import discover_root

UNCERTAIN = "光交换机和 KV 卸载哪个更急"
KV = [(ALICE, "KV cache 卸载到内存的方案怎么做"), (BOB, "有没有人做过分层卸载"), (ALICE, "我记得有篇讲 CXL 内存池的")]
SMALL_TALK = [(ALICE, "午饭吃什么"), (BOB, "楼下那家面馆"), (ALICE, "走吧")]


@pytest.fixture
def world(tmp_path):
    install_assistant()
    return World(tmp_path)


def run_cli(world, capsys, *args):
    """Run one ``assistant`` command against the world's repository and state."""

    code = cli.main(["--root", str(world.root), "assistant", "--state-dir", str(world.state), *args])
    captured = capsys.readouterr()
    assert captured.out.strip(), f"nothing on stdout; stderr said: {captured.err.strip()[-400:]}"
    return code, json.loads(captured.out)


# ---- what the assistant responds to ----


def test_modes_only_take_their_own_values(world, capsys):
    code, policy = run_cli(world, capsys, "mode", "proactive", "auto")
    assert (code, policy["proactive"]) == (0, "auto")
    code, policy = run_cli(world, capsys, "mode", "explicit", "off")
    assert (code, policy["explicit"], policy["proactive"]) == (0, False, "auto")

    with pytest.raises(SystemExit):
        run_cli(world, capsys, "mode", "proactive", "sometimes")
    assert Policy.load(world.store).proactive == "auto"


def test_mute_takes_a_duration_and_lifts_with_off(world, capsys):
    code, muted = run_cli(world, capsys, "mute", "90m")
    assert code == 0 and 5390 <= muted["muted_for_seconds"] <= 5400
    code, lifted = run_cli(world, capsys, "mute", "off")
    assert (code, lifted["muted_for_seconds"]) == (0, 0)
    code, failed = run_cli(world, capsys, "mute", "later")
    assert code == 1 and "Not a duration" in failed["error"]


def test_the_whitelist_lives_in_the_ignored_local_config(world, capsys):
    other = "oc_" + "7" * 32
    assert run_cli(world, capsys, "chat", "list") == (0, {"chats": []})
    code, added = run_cli(world, capsys, "chat", "add", other)
    assert code == 0 and added["chats"] == [other]
    assert AssistantConfig.load(world.root, world.state).chat_whitelist == (other,)
    assert (world.state / "config.local.yaml").is_file()
    assert run_cli(world, capsys, "chat", "add", other)[1]["chats"] == [other]
    assert run_cli(world, capsys, "chat", "remove", other)[1]["chats"] == []
    assert run_cli(world, capsys, "chat", "add", "not-a-chat")[0] == 1


# ---- the host session's loop ----


def test_tasks_wait_card_and_apply_form_the_host_sessions_loop(world, capsys, monkeypatch):
    monkeypatch.setattr(tasks, "TASK_BATCH_MIN_AGE_SECONDS", 0)
    live = Engine(world.store, world.index, world.config, world.root, world.state, bot_ids=("ou_bot",))
    live.ingest(
        Trigger("om_cli", CHAT, ALICE, int(time.time() * 1000), UNCERTAIN, "event", is_mention=True)
    )

    code, waiting = run_cli(world, capsys, "tasks", "wait", "--timeout", "5")
    assert (code, waiting["reason"], len(waiting["tasks"])) == (0, "tasks_ready", 1)
    card = waiting["tasks"][0]
    assert card["steps"] == tasks.CARD_STEPS and waiting["next"] == tasks.NEXT_STEP
    assert run_cli(world, capsys, "tasks", "card", "--task", card["task_id"]) == (0, card)

    row = tasks.get(world.store, card["task_id"])
    Path(card["output"]).write_text(json.dumps(world.refinement(row), ensure_ascii=False), encoding="utf-8")
    assert run_cli(world, capsys, "tasks", "apply", "--task", card["task_id"]) == (0, {"ok": True, "outcome": "refined"})
    assert run_cli(world, capsys, "tasks", "apply", "--task", card["task_id"])[0] == 1  # already applied
    assert run_cli(world, capsys, "tasks", "apply", "--task", "refine-nope") == (1, {"error": "Unknown task: refine-nope"})


def test_wait_returns_at_once_when_nothing_is_pending(world, capsys):
    code, waiting = run_cli(world, capsys, "tasks", "wait", "--timeout", "0.5")
    assert (code, waiting["reason"], waiting["next"]) == (0, "no_tasks", tasks.NEXT_STEP)


# ---- watching ----


def test_status_and_stop_with_nothing_running(world, capsys):
    code, report = run_cli(world, capsys, "status")
    assert code == 1 and report["service"]["running"] is False and report["self_check"]["ok"]
    assert run_cli(world, capsys, "stop") == (0, {"running": False, "stopped": True})


def test_review_and_stats_show_what_was_decided_including_the_silences(world, capsys):
    world.speak(KV)
    silent = world.look(SMALL_TALK)
    world.apply(silent, world.contribution(silent, act="none"))

    code, listed = run_cli(world, capsys, "review", "--days", "365")
    assert code == 0 and listed["by_act"] == {"add": {"said": 1}, "none": {"silent": 1}}
    assert sorted((item["act"], item["outcome"]) for item in listed["decisions"]) == [("add", "said"), ("none", "silent")]
    assert run_cli(world, capsys, "review", "--act", "none", "--days", "365")[1]["decisions"][0]["draft"] is None
    said = run_cli(world, capsys, "review", "--act", "add", "--days", "365")[1]["decisions"][0]
    assert said["draft"].startswith("日报库里有一条相关的：") and said["documents"][0]["id"].startswith("item:")

    code, counts = run_cli(world, capsys, "stats", "--days", "365")
    assert code == 0
    assert counts["acts"] == {"add": {"said": 1}, "none": {"silent": 1}}
    assert counts["dispositions"] == {"spoken": {"add:said": 3}, "silent": {"none:silent": 3}}
    assert counts["outbox"]["recommendation"] == {"sent": 1}
    assert counts["reports"] == {} and counts["pauses"] == []


def test_a_session_searches_for_its_own_task_and_may_cite_what_it_finds(world, capsys):
    task = world.look(KV)
    assert run_cli(world, capsys, "search", "--task", task["task_id"], "存储介质")[1]["hits"][0]["id"] == "roadmap:storage"
    assert tasks.seen_ids(world.store, task["task_id"]) == {"roadmap:storage"}
    assert run_cli(world, capsys, "search", "--task", "no-such-task", "存储介质")[0] == 1


def test_reports_go_to_the_owner_the_user_names_and_can_be_read_back(world, capsys, monkeypatch):
    opened = {}

    class FakeClient:
        def open_direct_chat(self, open_id: str, text: str) -> dict:
            opened.update(open_id=open_id, text=text)
            return {"chat_id": "oc_dm", "message_id": "om_dm"}

    monkeypatch.setattr(commands, "LarkClient", lambda config: FakeClient())
    owner = "ou_" + "a" * 32
    assert run_cli(world, capsys, "report", "to", owner) == (0, {"report_to": {"open_id": owner, "chat_id": "oc_dm"}})
    assert opened["open_id"] == owner and "向你汇报" in opened["text"]
    assert run_cli(world, capsys, "report", "to", "not-an-open-id")[0] == 1

    task = world.look([(ALICE, "我们在评估一个新方向")])
    world.apply(task, world.contribution(task, act="gap"))
    listing = run_cli(world, capsys, "report", "list", "--days", "365")[1]
    assert listing["report_to"]["chat_id"] == "oc_dm"
    assert [(item["kind"], item["status"], item["names"]) for item in listing["reports"]] == [("gap", "queued", ["同事 A"])]
    shown = run_cli(world, capsys, "report", "show", listing["reports"][0]["id"])[1]
    assert shown["messages"] == ["我们在评估一个新方向"] and shown["terms"] == ["新检索词"]
    assert run_cli(world, capsys, "report", "show", "no-such-report")[0] == 1


# ---- the live run's guard rails ----


def test_sec_03_the_live_run_refuses_every_group_but_the_test_group(world, capsys):
    code, refused = run_cli(world, capsys, "e2e", "--live", "--chat", "oc_" + "7" * 32)
    assert code == 2 and "refuses" in refused["error"]
    assert not (world.state / "service.pid").exists() and world.transport.calls == 0
    assert e2e.check_chat(None) == e2e.check_chat(e2e.LIVE_CHAT) == e2e.LIVE_CHAT
    with pytest.raises(e2e.E2EError, match="refuses"):
        e2e.check_chat("oc_" + "7" * 32)


def test_sec_04_the_published_config_carries_no_test_switches():
    data = yaml.safe_load((discover_root() / "config" / "group-assistant.yaml").read_text(encoding="utf-8"))
    assert set(data) == {"site_base_url", "lark_cli", "working_hours", "working_days"}
    assert data["site_base_url"] == "https://qiliangli.github.io/technical-briefing-skill/"
