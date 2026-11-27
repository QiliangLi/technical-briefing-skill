"""Replay tests for proactive recommendations, policy versions and reply gates (REC, POL, GATE)."""

import json
import re
from datetime import datetime

import pytest

from assistant_support import ALICE, BOB, CHAT, World
from briefing_skill.assistant import outbox
from briefing_skill.assistant.constants import DAILY_PROACTIVE_CAP
from briefing_skill.assistant.policy import Policy
from briefing_skill.assistant.replies import compose_answer, compose_recommendation, within_limit

# The address inside a markdown link, without its closing parenthesis.
LINK = re.compile(r"\]\((https?://\S+?)\)")

KV = [(ALICE, "KV cache 卸载到内存的方案怎么做"), (BOB, "有没有人做过分层卸载"), (ALICE, "我记得有篇讲 CXL 内存池的")]
OPTICS = [(ALICE, "光交换机在智算中心怎么调度"), (BOB, "光交换机的尾延迟"), (ALICE, "整负载调度光交换机")]
COOLING = [(ALICE, "液冷 manifold 那篇讲了什么"), (BOB, "manifold 进入 AI 工厂"), (ALICE, "液冷怎么部署")]
SMALL_TALK = [(ALICE, "午饭吃什么"), (BOB, "楼下那家面馆"), (ALICE, "走吧")]
SATURDAY = datetime(2026, 10, 10, 10, 0, 0).timestamp()


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def _queue(world, key, kind, reply_to, text, thread_key=None):
    """Put a row into the outbox the way a misbehaving writer would."""

    with world.store.transaction() as connection:
        outbox.enqueue(
            world.store, connection, key=key, kind=kind, chat_id=CHAT, reply_to=reply_to, text=text,
            thread_key=thread_key, now=world.now,
        )


# ---- Proactive recommendations ----


def test_rec_01_the_shape_gate_decides_what_is_assessed(world):
    world.policy(proactive="auto")

    world.discuss(KV[:2])
    world.advance(91)
    world.engine.sweep()
    assert world.reasons() == {"too_few_messages"}

    world.new_topic()
    world.discuss([(ALICE, "第一句"), (ALICE, "第二句"), (ALICE, "第三句"), (ALICE, "第四句")])
    world.advance(91)
    world.engine.sweep()
    assert world.reasons() == {"too_few_messages", "single_speaker"}

    world.new_topic()
    world.discuss(KV)
    world.advance(60)
    world.engine.sweep()
    assert world.tasks() == []

    world.advance(31)
    world.engine.sweep()
    assert len(world.tasks(kind="assess")) == 1
    assert world.reasons("evaluating") == {"assessment_created"}


def test_rec_02_a_thread_cools_down_for_a_day(world):
    world.policy(proactive="auto")
    root = world.recommend(KV)["reply_to"]
    world.discuss([(BOB, "第二轮的第一句"), (ALICE, "第二轮的第二句"), (BOB, "第三句")], root=root)
    world.advance(91)
    world.engine.sweep()
    assert world.reasons("ignored") == {"thread_cooldown"}
    assert world.tasks() == []


def test_rec_02_the_fourth_recommendation_of_the_day_is_held_back(world):
    for lines in (KV, OPTICS, COOLING):
        world.recommend(lines)
    world.new_topic()
    world.discuss([(BOB, "第四个话题的第一句"), (ALICE, "第二句"), (BOB, "第三句")])
    world.advance(91)
    assert world.engine.sweep()["paused"] == 1
    assert world.reasons("ignored") == {"daily_cap"}
    assert len(world.outbox_rows()) == DAILY_PROACTIVE_CAP


def test_rec_03_recommendations_wait_for_working_hours(world):
    world.now = SATURDAY
    world.policy(proactive="auto")
    world.discuss(KV)
    world.advance(91)
    world.engine.sweep()
    assert world.reasons() == {"outside_working_hours"}
    assert world.tasks() == []


def test_rec_04_observe_mode_records_what_it_would_accept_and_sends_nothing(world):
    task = world.quiet_discussion(KV, proactive="observe")
    assert world.apply(task, world.assessment(task))["outcome"] == "observe_would_accept"
    world.flush()
    assert world.outbox_rows() == [] and world.transport.calls == 0
    decision = world.store.fetchone("SELECT * FROM decisions WHERE kind='assess'")
    assert (decision["outcome"], decision["mode"]) == ("observe_would_accept", "observe")
    assert decision["draft"].startswith("这个方向")


def test_rec_05_auto_mode_recommends_one_document_in_one_sentence(world):
    sent = world.recommend(KV)
    assert (sent["chat_id"], sent["reply_to"]) == (CHAT, "om_1")
    assert sent["text"].startswith("这个方向日报里有一篇相关的：**")
    assert sent["text"].count("[查看详情](") == 1 and "\n" not in sent["text"]
    assert within_limit(sent["text"])
    thread = world.store.fetchone("SELECT * FROM threads")
    assert (thread["last_recommended_ms"], thread["root_message_id"]) == (int(world.now * 1000), "om_1")


def test_rec_06_no_matching_rule_means_silence(world):
    task = world.quiet_discussion(SMALL_TALK)
    assert world.apply(task, world.assessment(task, matched=(), doc_id=None))["outcome"] == "silent_no_rule"
    world.flush()
    assert world.outbox_rows() == []
    decision = world.store.fetchone("SELECT * FROM decisions WHERE kind='assess'")
    assert [rule["matches"] for rule in json.loads(decision["rules_json"])] == [False, False]
    assert decision["draft"] is None


def test_rec_07_an_evidence_quote_that_is_not_verbatim_is_rejected(world):
    task = world.quiet_discussion(KV)
    result = world.apply(task, world.assessment(task, quote="这句原话并不存在于讨论之中"))
    assert result == {"ok": False, "errors": ["evidence_quote is not verbatim for rule prior_art"]}
    world.flush()
    assert world.outbox_rows() == []
    assert world.reasons("ignored") == {"assess_invalid"}


def test_rec_08_an_assessment_that_never_ran_is_dropped(world):
    task = world.quiet_discussion(KV)
    world.advance(301)
    world.engine.sweep()
    world.flush()
    assert world.store.fetchone("SELECT status FROM tasks WHERE task_id=?", (task["task_id"],))["status"] == "expired"
    assert world.reasons("ignored") == {"assess_expired"}
    assert world.outbox_rows() == []


def test_rec_09_a_dislike_opts_that_discussion_out(world):
    world.policy(proactive="auto")
    root = world.say("KV cache 卸载到内存的方案怎么做")
    world.say("有没有人做过分层卸载", sender=BOB, root=root["message_id"])
    world.say("我记得有篇讲 CXL 内存池的", root=root["message_id"])
    world.advance(91)
    world.engine.sweep()
    task = world.tasks(kind="assess")[0]
    world.apply(task, world.assessment(task))
    world.flush()
    message_id = world.outbox_rows()[0]["message_id"]

    assert world.engine.on_reaction({"message_id": message_id, "emoji": "ThumbsDown", "operator_id": ALICE})["recorded"]
    world.say("第二轮的第一句", sender=BOB, root=root["message_id"])
    world.say("第二轮的第二句", root=root["message_id"])
    world.say("第二轮的第三句", sender=BOB, root=root["message_id"])
    world.advance(91)
    world.engine.sweep()
    assert world.reasons("ignored") == {"thread_muted"}
    assert len(world.outbox_rows()) == 1


def test_rec_10_a_global_mute_pauses_until_it_expires(world):
    policy = world.policy(proactive="auto")
    policy.muted_until = world.now + 600
    policy.save(world.store)
    world.discuss(KV)
    world.advance(91)
    world.engine.sweep()
    assert world.reasons("ignored") == {"muted"}

    world.advance(511)
    world.discuss([(BOB, "静音过后的第一句"), (ALICE, "第二句"), (BOB, "第三句")])
    world.advance(91)
    world.engine.sweep()
    assert len(world.tasks(kind="assess")) == 1


def test_rec_11_a_discussion_under_an_idea_card_needs_one_message_and_carries_the_idea(world):
    world.store.execute(
        "INSERT INTO registry(message_id, idea_id, issue_date, pushed_at) VALUES('om_card', 'idea_c', '2026-10-01', '2026-10-06T10:00:00')"
    )
    payload = world.task_input(world.quiet_discussion([(ALICE, "这个 idea 我们组之前试过类似的")], root="om_card"))
    assert payload["anchored_idea"]["id"] == "idea:idea_c"
    assert world.store.fetchone("SELECT anchor_idea_id FROM threads")["anchor_idea_id"] == "idea_c"


def test_rec_12_reaching_the_daily_cap_turns_proactive_mode_off(world):
    for lines in (KV, OPTICS, COOLING):
        world.recommend(lines)
    assert world.engine.sweep()["paused"] == 1
    assert Policy.load(world.store).proactive == "off"
    assert [row["reason"] for row in world.store.fetchall("SELECT reason FROM pause_log")] == ["daily_cap"]
    assert len(world.outbox_rows()) == DAILY_PROACTIVE_CAP


def test_rec_12_a_run_of_dislikes_turns_proactive_mode_off(world):
    world.policy(proactive="auto")
    for _ in range(2):
        world.say("KV cache 分层卸载怎么做", mention=True)
    world.flush()
    for row in world.outbox_rows():
        world.engine.on_reaction({"message_id": row["message_id"], "emoji": "THUMBSUP", "operator_id": ALICE})
        world.engine.on_reaction({"message_id": row["message_id"], "emoji": "ThumbsDown", "operator_id": BOB})
    assert Policy.load(world.store).proactive == "off"
    assert [row["reason"] for row in world.store.fetchall("SELECT reason FROM pause_log")] == ["dislike_ratio"]
    assert len(world.store.fetchall("SELECT * FROM feedback")) == 4


# ---- Rules and policy version ----


def test_pol_01_a_disabled_rule_is_neither_judged_nor_accepted(world):
    task = world.quiet_discussion(KV, related_evidence=False)
    assert [rule["id"] for rule in world.task_input(task)["rules"]] == ["prior_art"]

    smuggled = world.assessment(task, matched=())
    smuggled["rules"].append({"rule_id": "related_evidence", "matches": True, "evidence_quote": "分层卸载", "reason": "被关掉的规则"})
    assert world.apply(task, smuggled) == {"ok": False, "errors": ["rules must cover exactly: prior_art"]}
    assert world.outbox_rows() == []


def _drop_one(rules):
    return rules[1:]


def _repeat_one(rules):
    return rules + rules[:1]


@pytest.mark.parametrize("break_rules", [_drop_one, _repeat_one], ids=["missing one", "one twice"])
def test_pol_02_each_enabled_rule_needs_exactly_one_verdict(world, break_rules):
    task = world.quiet_discussion(KV)
    output = world.assessment(task)
    result = world.apply(task, {**output, "rules": break_rules(output["rules"])})
    assert result["ok"] is False and result["errors"] == ["rules must cover exactly: prior_art, related_evidence"]
    assert world.outbox_rows() == []


def test_pol_03_the_policy_version_changes_and_every_decision_carries_it(world):
    default = Policy.load(world.store)
    narrowed = world.policy(proactive="auto", related_evidence=False)
    assert default.version != narrowed.version != world.policy(proactive="auto").version
    assert narrowed.version == world.policy(proactive="auto", related_evidence=False).version

    task = world.quiet_discussion(KV, related_evidence=False)
    assert task["policy_version"] == narrowed.version
    world.apply(task, world.assessment(task, matched=()))
    assert {row["policy_version"] for row in world.store.fetchall("SELECT policy_version FROM decisions")} == {narrowed.version}


def test_pol_04_a_policy_change_voids_tasks_in_flight(world):
    world.say("光交换机和 KV 卸载哪个更急", mention=True)
    task = world.quiet_discussion(KV)
    world.policy(proactive="auto", prior_art=False)
    world.engine.sweep()

    statuses = {row["kind"]: row["status"] for row in world.store.fetchall("SELECT * FROM tasks")}
    assert statuses == {"assess": "invalid", "refine": "invalid"}
    assert world.reasons() >= {"assess_policy_changed", "refine_policy_changed"}
    world.flush()
    assert "没能细查" in world.sent()[0]
    assert world.apply(task, world.assessment(task))["ok"] is False


def test_pol_05_mode_and_rules_only_follow_local_commands(world):
    before = Policy.load(world.store)
    world.say("assistant mode proactive auto")
    world.say("assistant mute 0")
    world.flush()
    assert Policy.load(world.store).version == before.version
    assert Policy.load(world.store).proactive == "off" and world.transport.calls == 0


# ---- Reply gates ----


def test_gate_01_a_reply_nobody_asked_for_is_refused_at_the_door(world):
    world.say("一个人发的普通消息")
    world.say("KV cache 分层卸载怎么做", mention=True, sender="ou_other_bot", bot=True)
    _queue(world, "answer:unaddressed", "answer", "om_1", "没人问的回答")
    _queue(world, "answer:bot", "answer", "om_2", "回答机器人的")
    _queue(world, "recommendation:unverified", "recommendation", "om_1", "没有决策记录的推荐", f"{CHAT}:om_1")

    assert world.flush() == {"sent": 0, "retry": 0, "gone": 0, "failed": 0, "refused": 3}
    assert world.transport.calls == 0
    reasons = {row["id"]: row["last_error"] for row in world.outbox_rows()}
    assert reasons["answer:unaddressed"] == "The message being answered did not come from a person addressing the assistant"
    assert reasons["answer:bot"] == "The message being answered did not come from a person addressing the assistant"
    assert reasons["recommendation:unverified"] == "No accepted assessment with a matching rule covers this recommendation"


def test_gate_01_a_recommendation_is_held_back_once_the_mode_leaves_auto(world):
    task = world.quiet_discussion(KV)
    world.apply(task, world.assessment(task))
    world.policy(proactive="off")
    assert world.flush()["refused"] == 1
    assert world.transport.calls == 0
    assert world.outbox_rows()[0]["last_error"] == "Proactive mode is no longer auto"


def test_gate_02_a_long_reply_is_shortened_first_and_refused_when_it_still_does_not_fit(world):
    long_doc = {**world.index.get("item:" + "a" * 24), "summary": "这是一句很长的结论。" * 40}
    answer = compose_answer([{"doc": long_doc}], refined=True)
    assert within_limit(answer) and "[查看详情](" in answer
    assert within_limit(compose_recommendation(long_doc))

    _queue(world, "answer:long", "answer", "om_1", "词" * 400)
    row = world.outbox_rows()[0]
    assert (row["status"], row["last_error"]) == ("refused", "Exceeds the IM word limit: 250 words")
    assert world.flush()["sent"] == 0 and world.transport.calls == 0


@pytest.mark.parametrize("field", ["reason", "evidence_quote"])
def test_gate_03_a_link_outside_the_index_is_rejected(world, field):
    task = world.quiet_discussion(KV)
    output = world.assessment(task)
    output["rules"][0][field] = "详见 https://arxiv.org/abs/2401.00001"
    result = world.apply(task, output)
    assert result["ok"] is False
    assert result["errors"][0] == "Output contains a link outside the index: https://arxiv.org/abs/2401.00001"
    assert world.outbox_rows() == []


def test_gate_03_and_04_a_mixed_day_leaves_only_answers_and_recommendations_with_index_links(world):
    world.say("KV cache 分层卸载怎么做", mention=True)
    world.say("zzqx vvwu jjkk", mention=True)
    world.apply(world.tasks(kind="refine")[0], world.refinement(world.tasks(kind="refine")[0], none=True))
    world.recommend(OPTICS)
    world.quiet_discussion(SMALL_TALK)
    world.apply(world.tasks(kind="assess")[0], world.assessment(world.tasks(kind="assess")[0], matched=(), doc_id=None))

    rows = world.outbox_rows()
    assert {row["kind"] for row in rows} == {"answer", "recommendation"} == set(outbox.ALLOWED_KINDS) - {"card"}
    links = {url for row in rows for url in LINK.findall(row["text"])}
    assert links and links <= {doc["url"] for doc in world.index.docs}
    assert all(within_limit(row["text"]) for row in rows)
    with pytest.raises(outbox.OutboxError, match="not allowed"):
        _queue(world, "progress", "progress", "om_1", "正在处理")


def test_gate_05_replies_take_the_language_of_the_discussion_and_open_with_no_identity(world):
    world.say("KV cache 分层卸载怎么做", mention=True)
    world.say("zzqx vvwu jjkk", mention=True)
    refine = world.tasks(kind="refine")[0]
    world.apply(refine, world.refinement(refine, none=True))
    world.recommend(OPTICS)
    for text in world.sent() + [row["text"] for row in world.outbox_rows()]:
        assert re.search(r"[\u3400-\u9fff]", text)
        assert not re.search("我是|作为|助手|机器人|assistant|AI", text)
