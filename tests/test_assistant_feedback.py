"""Tests for idea cards: selection, confirmation before sending, copy tasks and the feedback ledger (FB)."""

import json

import pytest

from assistant_support import ALICE, BOB, BOT, CHAT, World
from briefing_skill import cli
from briefing_skill.assistant import feedback, install_assistant, lark
from briefing_skill.assistant.events import card_action
from briefing_skill.utils import write_json

ISSUE = "2026-10-20"


def idea(idea_id, *, first_seen="2026-10-01", status="observing", log=(), evidence=()):
    return {
        "schema_version": 1, "idea_id": idea_id, "title": f"想法 {idea_id}", "problem": "问题。", "hypothesis": "假设。",
        "mechanism": "机制。", "expected_effect": "预期效果。", "topic_ids": ["tpn"], "status": status,
        "evidence_for": [{"item_id": f"e{index}", "issue_date": seen, "reason": f"证据 {index}"} for index, seen in enumerate(evidence)],
        "evidence_against": [], "first_seen_issue": first_seen, "last_updated_issue": ISSUE, "decision_log": list(log),
    }


def moved(idea_id):
    return {"event_id": f"ev_{idea_id}", "issue_date": ISSUE, "decision": "status_changed", "from_status": "seed", "to_status": "observing"}


def publish(world, ideas):
    folder = world.root / "knowledge" / "ideas"
    for path in folder.glob("*.json"):
        path.unlink()
    for idea_id, content in ideas.items():
        write_json(folder / f"{idea_id}.json", content)


def shown_before(world, idea_id, issue="2026-09-01"):
    world.store.execute(
        "INSERT INTO registry(message_id, idea_id, issue_date, pushed_at) VALUES(?, ?, ?, ?)",
        (f"sent_card:{issue}:{idea_id}", idea_id, issue, f"{issue}T10:00:00"),
    )


def push(world, issue=ISSUE, confirm=True):
    return feedback.push(world.root, world.config, world.state, world.store, issue, world.transport, confirm=confirm, now=world.now)


@pytest.fixture
def world(tmp_path):
    install_assistant()
    return World(tmp_path)


# ---- choosing ----


def test_fb_01_at_most_three_cards_change_first_then_new_then_one_revived(world):
    ideas = {
        "b": idea("b", evidence=[ISSUE]),
        "a": idea("a", log=[moved("a")]),
        "c": idea("c", first_seen=ISSUE),
        "d": idea("d", first_seen=ISSUE),
        "e": idea("e"),
        "f": idea("f"),
        "g": idea("g"),
    }
    publish(world, ideas)
    shown_before(world, "f")
    world.store.execute(
        "INSERT INTO feedback(id, message_id, idea_id, choice, operator_id, source, created_at) VALUES('om_g:x', 'om_g', 'g', 'worth_validating', 'ou_x', 'button', '2026-10-01T10:00:00')"
    )

    plan = feedback.prepare(world.root, world.config, world.state, world.store, ISSUE, world.now)
    assert plan["selection"] == {"changed": ["a", "b"], "created": ["c", "d"], "revived": ["f"], "selected": ["a", "b", "c"]}
    assert [(item["idea_id"], item["copy"]) for item in plan["cards"]] == [("a", "stored"), ("b", "stored"), ("c", "stored")]
    assert len(plan["copy_tasks"]) == 3

    publish(world, {name: ideas[name] for name in ("a", "c", "e", "f")})
    plan = feedback.prepare(world.root, world.config, world.state, world.store, ISSUE, world.now)
    assert plan["selection"]["selected"] == ["a", "c", "f"]  # f was shown before and nobody answered; e waits for its turn

    shown_before(world, "a", ISSUE)
    plan = feedback.prepare(world.root, world.config, world.state, world.store, ISSUE, world.now)
    assert "a" not in plan["selection"]["selected"]  # already shown for this issue


def test_fb_02_nothing_is_sent_without_confirmation(world):
    publish(world, {"a": idea("a", log=[moved("a")]), "e": idea("e")})
    report = push(world, confirm=False)
    assert "Preview only" in report["note"] and [item["idea_id"] for item in report["cards"]] == ["a", "e"]
    assert world.transport.calls == 0 and world.outbox_rows() == []
    assert world.store.fetchall("SELECT * FROM registry") == []


def test_fb_07_each_card_is_sent_once_and_the_week_is_held(world):
    ideas = {"a": idea("a", log=[moved("a")]), "b": idea("b", first_seen=ISSUE), "e": idea("e")}
    publish(world, ideas)

    first = push(world)
    assert first["sent"] == ["a", "b", "e"] and first["delivery"] == {"a": "sent", "b": "sent", "e": "sent"}
    assert [(item["kind"], item["chat_id"], item["reply_to"]) for item in world.transport.sent] == [("card", CHAT, "")] * 3
    assert sorted(row["message_id"] for row in world.store.fetchall("SELECT message_id FROM registry")) == [
        f"sent_card:{ISSUE}:a", f"sent_card:{ISSUE}:b", f"sent_card:{ISSUE}:e"
    ]

    again = push(world)
    assert (again["sent"], again["cards"]) == ([], []) and len(world.transport.sent) == 3  # everything is inside the weekly interval

    publish(world, {**ideas, "h": idea("h", first_seen="2026-10-22")})
    soon = push(world, "2026-10-22")
    assert soon["sent"] == [] and "on or after 2026-10-27" in soon["error"] and len(world.transport.sent) == 3

    later = push(world, "2026-10-27")
    assert later["sent"] == ["h"] and len(world.transport.sent) == 4


# ---- the card and its copy ----


def copy_output(task, **overrides):
    return {
        "schema_version": 1, "_task": {"task_id": task["task_id"], "kind": "card_copy"},
        "headline": "把同样的开头复制到多个节点", "summary": "同样的开头被反复计算，复制一份就能少算。",
        "why_it_matters": "能省下重复的首包计算。", **overrides,
    }


def test_fb_08_the_copy_comes_from_a_session_task_and_the_card_is_built_from_it(world):
    publish(world, {"a": idea("a", evidence=["2026-10-10"])})
    plan = feedback.prepare(world.root, world.config, world.state, world.store, ISSUE, world.now)
    task = world.tasks(kind="card_copy")[0]
    assert list(world.task_input(task)) == ["_task", "idea"]
    assert "decision_log" not in world.task_input(task)["idea"]

    world.policy(proactive="auto")  # a mode change does not void card copy
    world.engine.sweep()
    assert [item["status"] for item in world.tasks(kind="card_copy")] == ["pending"]

    assert world.apply(task, copy_output(task, summary="依据 validation_plan 里的 decision_log"))["ok"] is False
    world.advance(1)
    feedback.prepare(world.root, world.config, world.state, world.store, ISSUE, world.now)
    other = world.tasks(kind="card_copy")[0]
    too_long = world.apply(other, copy_output(other, headline="标" * 41))["errors"]
    assert len(too_long) == 1 and too_long[0].startswith("headline:") and "is too long" in too_long[0]

    publish(world, {"a": idea("a", evidence=["2026-10-10"])})
    world.advance(1)
    feedback.prepare(world.root, world.config, world.state, world.store, ISSUE, world.now)
    task = world.tasks(kind="card_copy")[0]
    assert world.apply(task, copy_output(task)) == {"ok": True, "outcome": "card_draft_stored", "idea_id": "a"}

    plan = feedback.prepare(world.root, world.config, world.state, world.store, ISSUE, world.now)
    assert plan["waiting_for_copy"] == [] and plan["copy_tasks"] == []
    item = plan["cards"][0]
    assert (item["copy"], item["headline"], item["evidence"]) == ("session", "把同样的开头复制到多个节点", "证据 0")
    assert item["url"] == f"{world.config.site_base_url}#ideas?idea=a" and item["status"] == "观察中，2026-10-01 起"

    push(world)
    sent = json.loads(world.transport.sent[-1]["text"])
    assert sent["schema"] == "2.0"
    assert sent["header"] == {"title": {"tag": "plain_text", "content": "把同样的开头复制到多个节点"}, "template": "blue"}
    elements = sent["body"]["elements"]
    assert [block["content"] for block in elements[:4]] == [
        "同样的开头被反复计算，复制一份就能少算。", "**为什么重要**：能省下重复的首包计算。",
        "**一条代表证据**：证据 0", f"**状态**：观察中，2026-10-01 起　[查看详情]({item['url']})",
    ]
    assert elements[-4:] == [
        {"tag": "button", "text": {"tag": "plain_text", "content": "值得投入验证"}, "type": "primary_filled",
         "behaviors": [{"type": "callback", "value": {"choice": "worth_validating", "idea": "a"}}]},
        {"tag": "button", "text": {"tag": "plain_text", "content": "不看好"}, "type": "default",
         "behaviors": [{"type": "callback", "value": {"choice": "not_promising", "idea": "a"}}]},
        {"tag": "button", "text": {"tag": "plain_text", "content": "证据不足"}, "type": "default",
         "behaviors": [{"type": "callback", "value": {"choice": "insufficient_evidence", "idea": "a"}}]},
        {"tag": "button", "text": {"tag": "plain_text", "content": "已有人做过"}, "type": "default",
         "behaviors": [{"type": "callback", "value": {"choice": "prior_art_exists", "idea": "a"}}]},
    ]
    assert len(elements) == 10  # no tally line before anything is received


def test_every_card_button_calls_back(world):
    """A card 1.0 button with only a ``value`` does nothing when pressed: the platform reports
    that there is no callback for it. Every verdict button must carry a callback behaviour."""
    publish(world, {"a": idea("a")})
    feedback.push(world.root, world.config, world.state, world.store, ISSUE, world.transport, confirm=True, now=world.now)
    sent = json.loads(world.transport.sent[-1]["text"])
    buttons = [element for element in sent["body"]["elements"] if element["tag"] == "button"]
    assert len(buttons) == 4
    for button in buttons:
        (behaviour,) = button["behaviors"]
        assert behaviour["type"] == "callback" and set(behaviour["value"]) == {"choice", "idea"}
        assert behaviour["value"]["choice"] in feedback.CARD_CHOICES and behaviour["value"]["idea"] == "a"


def test_a_press_is_shown_on_the_card(world, monkeypatch):
    patched = []
    monkeypatch.setattr(feedback.lark, "patch_card", lambda config, message_id, card: patched.append((message_id, card)))
    publish(world, {"a": idea("a")})
    feedback.push(world.root, world.config, world.state, world.store, ISSUE, world.transport, confirm=True, now=world.now)
    card_message = world.store.fetchone("SELECT message_id FROM registry")["message_id"]

    world.engine.on_card_action({"message_id": card_message, "choice": "insufficient_evidence", "operator_id": "ou_x"})
    world.engine.on_card_action({"message_id": card_message, "choice": "worth_validating", "operator_id": "ou_y"})
    world.engine.on_reaction({"message_id": card_message, "emoji": "THUMBSUP", "operator_id": "ou_z"})
    assert feedback.tally(world.store, card_message) == {
        "worth_validating": 2, "not_promising": 0, "insufficient_evidence": 1, "prior_art_exists": 0
    }

    assert feedback.refresh_card(world.store, world.root, world.config, card_message)
    message_id, card = patched[-1]
    assert message_id == card_message
    closing = json.loads(card)["body"]["elements"][-1]
    assert closing["content"] == "已收到 3 条反馈：值得投入验证 ×2，证据不足 ×1"
    assert not feedback.refresh_card(world.store, world.root, world.config, "om_unknown")


# ---- the ledger ----


def card_message(world, idea_id="a"):
    world.store.execute(
        "INSERT INTO registry(message_id, idea_id, issue_date, pushed_at) VALUES('om_card', ?, ?, '2026-10-20T10:00:00')",
        (idea_id, ISSUE),
    )


def test_fb_04_a_button_press_on_a_card_is_recorded_with_its_operator(world):
    card_message(world)
    press = card_action(
        {
            "type": "card.action.trigger", "event_id": "e1", "action_tag": "button", "action_name": "card", "action_value": '{"choice":"insufficient_evidence","idea":"a"}',
            "message_id": "om_card", "chat_id": CHAT, "operator_id": ALICE, "token": "t", "timestamp": "1",
        }
    )
    assert world.engine.on_card_action(press) == {"recorded": True, "idea_id": "a", "choice": "insufficient_evidence"}
    assert world.engine.on_card_action({**press, "operator_id": ALICE})["recorded"] is True  # pressing twice is still one verdict
    assert world.engine.on_card_action({**press, "message_id": "om_unknown"})["recorded"] is False
    assert world.engine.on_card_action({**press, "operator_id": BOT})["recorded"] is False
    assert len(world.store.fetchall("SELECT * FROM feedback")) == 1


def test_fb_05_a_reaction_on_a_card_counts_as_one_of_the_two_verdicts_it_can_express(world):
    card_message(world)
    up = {"message_id": "om_card", "emoji": "THUMBSUP", "operator_id": ALICE}
    assert world.engine.on_reaction(up) == {"recorded": True, "choice": "worth_validating", "paused": 0}
    assert world.engine.on_reaction({**up, "emoji": "SMILE"}) == {"recorded": False}
    assert world.engine.on_reaction({**up, "removed": True}) == {"removed": True}
    assert world.store.fetchall("SELECT * FROM feedback") == []


class ReactionSource:
    """Stands in for Feishu's reaction lists, in the shape the API returns."""

    def __init__(self):
        self.lists: dict[str, list[dict]] = {}

    def reactions(self, message_id):
        if self.lists.get(message_id) is None:
            raise lark.LarkError("field validation failed")
        return self.lists.get(message_id, [])


def reaction(operator_id, emoji):
    return {"reaction_id": f"r_{operator_id}_{emoji}", "operator": {"operator_id": operator_id, "operator_type": "user"},
            "action_time": "1", "reaction_type": {"emoji_type": emoji}}


def test_fb_06_collect_makes_the_ledger_match_what_feishu_shows(world):
    publish(world, {"a": idea("a", log=[moved("a")]), "b": idea("b", first_seen=ISSUE)})
    push(world)
    source = ReactionSource()
    first, second = f"sent_card:{ISSUE}:a", f"sent_card:{ISSUE}:b"
    source.lists[first] = [reaction(ALICE, "THUMBSUP"), reaction(BOB, "SMILE")]
    source.lists[second] = [reaction(BOB, "ThumbsDown")]

    assert feedback.collect(world.store, source, world.now) == {"cards": 2, "added": 2, "removed": 0, "unreadable": 0}
    assert feedback.collect(world.store, source, world.now) == {"cards": 2, "added": 0, "removed": 0, "unreadable": 0}

    source.lists[first] = [reaction(ALICE, "THUMBSUP"), reaction(ALICE, "ThumbsDown")]
    source.lists[second] = []
    assert feedback.collect(world.store, source, world.now) == {"cards": 2, "added": 1, "removed": 1, "unreadable": 0}

    source.lists[second] = None  # Feishu refuses to answer for one card: it is counted, not taken for silence
    assert feedback.collect(world.store, source, world.now) == {"cards": 2, "added": 0, "removed": 0, "unreadable": 1}

    assert feedback.summary(world.store) == {
        "ideas": {"a": {"worth_validating": 1, "not_promising": 1, "insufficient_evidence": 0, "prior_art_exists": 0, "people": 1}},
        "pushes": [{"issue_date": ISSUE, "cards": 2, "pushed_at": "2026-10-06T10:00:00+08:00"}],
        "unsent_cards": 0,
    }


# ---- the command ----


def test_the_feedback_commands_share_the_assistants_state(world, capsys):
    publish(world, {"a": idea("a", log=[moved("a")])})

    def run(*args):
        code = cli.main(["--root", str(world.root), "feedback", "--state-dir", str(world.state), *args])
        return code, json.loads(capsys.readouterr().out)

    assert run("push", "--issue", ISSUE)[0] == 0 and world.transport.calls == 0  # a push without confirmation is a preview
    assert run("prepare", "--issue", "2026-10-30")[1]["copy_tasks"]
    assert run("prepare", "--issue", "yesterday")[0] == 1
    assert run("status")[1]["pushes"] == []
