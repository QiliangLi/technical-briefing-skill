"""Tests for the simulated discussions and the checks on what the assistant says about them."""

import json
from pathlib import Path

import pytest

from assistant_support import ALICE, BOB, SITE, World
from briefing_skill import cli
from briefing_skill.assistant import commands, discussions, install_assistant
from briefing_skill.assistant.config import AssistantConfig
from briefing_skill.assistant.constants import DEBOUNCE_SECONDS
from briefing_skill.assistant.retrieval import ensure_index
from briefing_skill.paths import discover_root

SPEAKING = {"id": "speaking", "title": "找先例", "target": "add", "messages": [{"from": "a", "text": "有人做过吗"}],
           "speak": True, "expect_any": ["卸载"], "avoid": ["Harness"]}
SILENT = {"id": "silent", "title": "闲聊", "speak": False, "expect_any": [], "avoid": []}
GOOD_REPLY = f"关于「换出显存」：**KV cache 分层卸载到内存与 SSD**（2026-10-01） [查看详情]({SITE}#archive?date=2026-10-01&item=a)"
OFF_TOPIC_REPLY = f"关于「换出显存」：**光交换机在智算中心的调度**（2026-10-01） [查看详情]({SITE}#archive?date=2026-10-01&item=b)"


def judged(scenario, replies):
    return discussions.evaluate(scenario, replies, site_base_url=SITE)


@pytest.fixture
def world(tmp_path):
    install_assistant()
    return World(tmp_path)


# ---- the checks ----


def test_a_good_reply_passes_and_each_fault_is_named():
    result = judged(SPEAKING, [GOOD_REPLY])
    assert result == {"ok": True, "spoke": True, "checks": {
        "speaks-when-it-should": True, "links-come-from-the-site": True, "cites-something-expected": True,
        "avoids-the-wrong-things": True, "short-enough": True,
    }}
    assert judged(SPEAKING, [OFF_TOPIC_REPLY])["checks"]["cites-something-expected"] is False
    assert judged(SPEAKING, [GOOD_REPLY.replace(SITE, "https://evil.test/")])["checks"]["links-come-from-the-site"] is False
    assert judged(SPEAKING, [GOOD_REPLY + " Harness-Zero"])["checks"]["avoids-the-wrong-things"] is False
    assert judged(SPEAKING, ["词" * (discussions.REPLY_CHAR_LIMIT + 1)])["checks"]["short-enough"] is False


def test_silence_is_judged_by_what_the_scenario_expects():
    assert judged(SPEAKING, [])["checks"]["speaks-when-it-should"] is False
    assert judged(SILENT, [])["ok"] is True
    assert judged(SILENT, [GOOD_REPLY])["ok"] is False


def test_the_report_shows_each_discussion_what_was_said_and_room_for_a_score():
    spoke = {"id": "a", "title": "找先例", "target": "add", "speak": True, "coverage": "reached",
             "messages": [{"from": "a", "text": "有人做过吗"}], "replies": [GOOD_REPLY], "seconds": 42,
             "why_silent": [], "evaluation": judged(SPEAKING, [GOOD_REPLY])}
    silent = {**spoke, "id": "b", "title": "闲聊", "target": "none", "speak": False, "replies": [], "seconds": None,
              "why_silent": ["ignored:single_speaker"], "evaluation": judged(SILENT, [])}
    silent.pop("coverage")
    page = discussions.report([spoke, silent], session="stand-in", generated_at=0)
    assert "共 2 个场景，2 个通过" in page and "替身会话按规则取第一条候选" in page
    assert "## 找先例（通过）" in page and "库里有，也检得到" in page and "- 同事 A：有人做过吗" in page
    assert "助手的回复，42 秒后：" in page and "> " + GOOD_REPLY in page
    assert "## 闲聊（通过）" in page and "助手没有回复。" in page and "去向记录：ignored:single_speaker" in page
    assert page.count("人工评分：____ / 5") == 2


# ---- the scenario file ----


def test_the_scenario_file_is_sound_and_covers_every_case():
    scenarios = discussions.load(discover_root())
    assert discussions.shape_problems(scenarios) == []
    assert {scenario["target"] for scenario in scenarios} == {"none", "add", "review", "gap"}
    assert {scenario["coverage"] for scenario in scenarios if "coverage" in scenario} == set(discussions.COVERAGES)
    assert {scenario["speak"] for scenario in scenarios} == {True, False}
    assert all(len(line["text"]) <= 400 for scenario in scenarios for line in scenario["messages"])
    assert discussions.shape_problems([{**SPEAKING, "coverage": "everywhere"}]) == ["speaking: coverage must be one of reached, missed, absent and needs expect_any"]


def test_what_the_corpus_holds_for_each_discussion_matches_its_label(tmp_path):
    """Measured against the real corpus. When this fails, retrieval or the corpus changed:
    measure again and update the scenario's `coverage`."""
    root = discover_root()
    index, _ = ensure_index(root, AssistantConfig.load(root), tmp_path / "state")
    for scenario in discussions.load(root):
        if "coverage" in scenario:
            assert discussions.coverage_of(index, scenario) == scenario["coverage"], scenario["id"]


# ---- a replay through the engine ----


def play(world, scenario):
    """Hold the discussion with two speakers and let a careful session answer it."""

    world.policy(proactive="auto")
    world.new_topic()
    speakers = {"a": ALICE, "b": BOB}
    sent = []
    for line in scenario["messages"]:
        result = world.say(
            line["text"], sender=speakers[line["from"]], root=sent[0] if sent else "", advance=scenario.get("gap_seconds", 1)
        )
        sent.append(result["message_id"])
    world.advance(DEBOUNCE_SECONDS + 1)
    world.engine.sweep()
    for task in world.tasks(kind="contribute"):
        world.apply(task, world.careful_contribution(task, scenario["expect_any"]))
    world.flush()
    return [row["text"] for row in world.outbox_rows() if row["reply_to"] == sent[0] and row["status"] == "sent"]


@pytest.mark.parametrize("name", ["kv-offload-prior-art", "lively-optical-switch"])
def test_a_discussion_the_small_corpus_covers_is_joined_within_seconds(world, name):
    scenario = next(item for item in discussions.load(discover_root()) if item["id"] == name)
    replies = play(world, scenario)
    assert len(replies) == 1 and judged(scenario, replies)["ok"], replies
    assert replies[0].startswith("日报库里有一条相关的：")  # the framing comes first, then the cited document


@pytest.mark.parametrize("name", ["small-talk", "admin-meeting"])
def test_small_talk_gets_no_reply(world, name):
    scenario = next(item for item in discussions.load(discover_root()) if item["id"] == name)
    assert play(world, scenario) == [] and judged(scenario, [])["ok"]


# ---- the command ----


def run_cli(world, capsys, *args):
    code = cli.main(["--root", str(world.root), "assistant", "--state-dir", str(world.state), "e2e", "--live", *args])
    return code, json.loads(capsys.readouterr().out)


def test_the_discussion_flags_are_checked_before_anything_is_sent(world, capsys):
    assert run_cli(world, capsys, "--only", "small-talk")[0] == 2  # --only narrows --discussions
    assert run_cli(world, capsys, "--discussions", "--only", "no-such-scenario") == (2, {"error": "Unknown scenarios: no-such-scenario"})
    assert world.transport.calls == 0 and not (world.state / "service.pid").exists()


def test_the_discussion_run_is_handed_the_scenarios_it_was_asked_for(world, capsys, monkeypatch):
    seen = {}

    class FakeLive:
        def __init__(self, root: Path) -> None:
            seen["root"] = root

        def discuss(self, scenarios, *, session: str, session_wait: float) -> dict:
            seen.update(ids=[scenario["id"] for scenario in scenarios], session=session, session_wait=session_wait)
            return {"ok": True, "results": [], "passed": 0, "report": "nowhere.md"}

    def run_from_repository(*args: str) -> int:
        return cli.main(["--root", str(discover_root()), "assistant", "--state-dir", str(world.state), "e2e", "--live", *args])

    monkeypatch.setattr(commands.e2e, "Live", FakeLive)
    assert run_from_repository("--discussions", "--session", "manual", "--session-wait", "300") == 0
    assert seen["root"] == discover_root() and len(seen["ids"]) == 13 and (seen["session"], seen["session_wait"]) == ("manual", 300.0)
    assert run_from_repository("--discussions", "--only", "small-talk,moe-expert-offload") == 0
    assert seen["ids"] == ["moe-expert-offload", "small-talk"] and seen["session"] == "stand-in"  # the file's order
