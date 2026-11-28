"""Tests for the assistant commands other than ``serve``, driven through the real CLI."""

import json
import time
from pathlib import Path

import pytest
import yaml

from assistant_support import ALICE, BOB, CHAT, World
from briefing_skill import cli
from briefing_skill.assistant import e2e, install_assistant, tasks
from briefing_skill.assistant.config import AssistantConfig
from briefing_skill.assistant.engine import Engine
from briefing_skill.assistant.events import Trigger
from briefing_skill.assistant.policy import Policy
from briefing_skill.paths import discover_root

UNCERTAIN = "光交换机和 KV 卸载哪个更急"
KV = [(ALICE, "KV cache 卸载到内存的方案怎么做"), (BOB, "有没有人做过分层卸载"), (ALICE, "我记得有篇讲 CXL 内存池的")]
OPTICS = [(ALICE, "光交换机在智算中心怎么调度"), (BOB, "光交换机的尾延迟"), (ALICE, "整负载调度光交换机")]


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


def test_rules_are_listed_and_switched_one_at_a_time(world, capsys):
    code, listed = run_cli(world, capsys, "rules")
    assert code == 0 and [rule["id"] for rule in listed["rules"]] == ["prior_art", "related_evidence"]
    assert all(rule["on"] for rule in listed["rules"])

    code, switched = run_cli(world, capsys, "rules", "related_evidence", "off")
    assert code == 0 and switched["version"] != listed["version"]
    assert [rule["on"] for rule in switched["rules"]] == [True, False]

    assert run_cli(world, capsys, "rules", "no_such_rule", "off")[0] == 1
    assert run_cli(world, capsys, "rules", "prior_art")[0] == 1  # a rule without on or off is not a switch


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


def test_review_and_stats_summarise_a_shadow_period(world, capsys):
    world.recommend(KV)
    task = world.quiet_discussion(OPTICS, proactive="observe")
    world.apply(task, world.assessment(task))

    code, listed = run_cli(world, capsys, "review", "--days", "365")
    assert code == 0
    assert [item["outcome"] for item in listed["decisions"]] == ["observe_would_accept", "recommended"]
    assert [item["rules"][0]["quote"] for item in listed["decisions"]] == ["整负载调度光", "我记得有篇讲"]
    assert listed["by_rule"]["prior_art"] == {"judged": 2, "matched": 2}
    assert run_cli(world, capsys, "review", "--days", "365", "--rule", "related_evidence")[1]["decisions"] == []

    code, counts = run_cli(world, capsys, "stats", "--days", "365")
    assert code == 0
    assert counts["decisions"]["assess"] == {"recommended": 1, "observe_would_accept": 1}
    assert counts["dispositions"] == {"recommended": {"recommended": 3}, "silent": {"observe_would_accept": 3}}
    assert counts["outbox"]["recommendation"] == {"sent": 1}
    assert counts["tasks"]["assess"] == {"applied": 2}
    assert counts["feedback"] == {} and counts["pauses"] == []


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
