"""Replay tests for looking at discussions, speaking in them, and the gates on what is said (JOIN, POL, GATE)."""

import json
import re
from datetime import datetime

import pytest

from assistant_support import ALICE, BOB, CHAT, SITE, World
from briefing_skill.assistant import feedback, outbox, tasks
from briefing_skill.assistant.constants import (
    BREAKER_LIMIT,
    DEBOUNCE_SECONDS,
    REPORTS_PER_DAY,
    SESSION_SEARCHES,
    THREAD_MIN_INTERVAL_SECONDS,
)
from briefing_skill.assistant.policy import Policy
from briefing_skill.assistant.replies import compose_answer, within_limit
from briefing_skill.assistant.timeutil import iso

KV = [(ALICE, "KV cache 卸载到内存的方案怎么做"), (BOB, "有没有人做过分层卸载"), (ALICE, "我记得有篇讲 CXL 内存池的")]
SMALL_TALK = [(ALICE, "午饭吃什么"), (BOB, "楼下那家面馆"), (ALICE, "走吧")]
OWNER = {"open_id": "ou_owner", "chat_id": "oc_dm"}
CONFIDENT = "KV cache 分层卸载怎么做"
LINK = re.compile(r"\]\((https?://\S+?)\)")


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def shown(world, task) -> set[str]:
    return {candidate["id"] for candidate in world.task_input(task)["candidates"]}


def queue(world, key, kind, reply_to, text, thread_key=None, chat_id=CHAT):
    with world.store.transaction() as connection:
        outbox.enqueue(
            world.store, connection, key=key, kind=kind, chat_id=chat_id, reply_to=reply_to, text=text,
            thread_key=thread_key, now=world.now,
        )


# ---- when a discussion is looked at ----


def test_join_01_a_discussion_is_looked_at_as_soon_as_it_opens_however_lively(world):
    world.policy(proactive="auto")
    world.new_topic()
    first = world.say("光交换机这周要定")
    world.advance(DEBOUNCE_SECONDS - 2)
    world.engine.sweep()
    assert world.tasks(kind="contribute") == []

    world.advance(2)
    world.engine.sweep()
    look = world.tasks(kind="contribute")[0]
    # The discussion keeps going while the session is still thinking.
    for text in ("关键是调度", "整负载调度好做", "尾延迟有数吗", "那把调度定下来"):
        world.say(text, sender=BOB, root=first["message_id"], advance=3)
    world.engine.sweep()

    assert [task["task_id"] for task in world.tasks(kind="contribute")] == [look["task_id"]]
    assert len(world.task_input(look)["messages"]) == 5, "Later messages were not folded into the open look"
    assert world.reasons("evaluating") == {"looking"}


def test_join_02_one_look_at_a_time_and_at_least_thirty_seconds_apart(world):
    look = world.look(KV)
    root = look["thread_key"].split(":", 1)[1]
    world.apply(look, world.contribution(look, act="none"))
    world.say("那 SSD 上放冷的这部分呢", root=root)

    world.advance(THREAD_MIN_INTERVAL_SECONDS - 2)
    world.engine.sweep()
    assert world.tasks(kind="contribute") == [], "A second look came too soon"

    world.advance(3)
    world.engine.sweep()
    assert len(world.tasks(kind="contribute")) == 1


def test_join_03_one_message_from_one_person_is_looked_at(world):
    task = world.look([(ALICE, "液冷这块现在怎么部署")])
    assert len(world.task_input(task)["messages"]) == 1


def test_join_12_a_discussion_under_a_card_carries_the_idea(world):
    world.store.execute(
        "INSERT INTO registry(message_id, idea_id, issue_date, pushed_at) VALUES('om_card', 'idea_c', '2026-10-01', '2026-10-06T10:00:00')"
    )
    payload = world.task_input(world.look([(ALICE, "这个 idea 我们组之前试过类似的")], root="om_card"))
    assert payload["anchored_idea"]["id"] == "idea:idea_c"
    assert payload["topics"] == []  # the small repository configures none


# ---- what it says ----


def test_join_04_observe_records_what_it_would_say_and_sends_nothing(world):
    task = world.look(KV, proactive="observe")
    assert world.apply(task, world.contribution(task))["outcome"] == "observe_would_say"
    world.flush()
    assert world.outbox_rows() == [] and world.transport.calls == 0
    decision = world.store.fetchone("SELECT * FROM decisions WHERE kind='contribute'")
    assert (decision["outcome"], decision["mode"], decision["act"]) == ("observe_would_say", "observe", "add")
    assert decision["draft"].startswith("日报库里有一条相关的：")


def test_join_05_it_joins_with_a_framing_and_cited_documents_in_the_thread(world):
    said = world.speak(KV)
    assert (said["kind"], said["reply_to"], said["chat_id"]) == ("recommendation", "om_1", CHAT)
    assert said["text"] == (
        "日报库里有一条相关的：\n• 📄 **KV cache 分层卸载到内存与 SSD**（2026-10-01）：把冷 KV 卸载到内存后吞吐提升。 "
        f"[查看详情]({SITE}#archive?date=2026-10-01&item=aaaaaaaaaaaaaaaaaaaaaaaa)"
    )
    assert within_limit(said["text"], "recommendation")
    assert world.store.fetchone("SELECT outcome, act FROM decisions WHERE kind='contribute'") == {"outcome": "said", "act": "add"}


def test_join_06_a_proposal_gets_a_structured_review(world):
    task = world.look([(ALICE, "我有个想法：把冷的 KV 放到内存里，热数据留在显存")])
    assert world.apply(task, world.contribution(task, act="review", framing="这个思路和日报库对得上："))["outcome"] == "said"
    world.flush()
    lines = world.sent()[-1].split("\n")
    assert lines[0] == "这个思路和日报库对得上："
    assert lines[1].startswith("支持它的证据：📄 **KV cache 分层卸载到内存与 SSD**（2026-10-01）：")
    assert lines[-1] == "库里还没找到的：库里没有对应内容"


def test_join_07_nothing_to_add_is_recorded_as_silence(world):
    task = world.look(SMALL_TALK)
    assert world.apply(task, world.contribution(task, act="none")) == {"ok": True, "outcome": "silent", "act": "none"}
    world.flush()
    assert world.outbox_rows() == [] and world.reasons("silent") == {"none:silent"}


def test_join_10_a_look_that_never_ran_ends_in_silence(world):
    task = world.look(KV)
    world.advance(901)
    world.engine.sweep()
    world.flush()
    assert world.store.fetchone("SELECT status FROM tasks WHERE task_id=?", (task["task_id"],))["status"] == "expired"
    assert world.reasons("silent") == {"contribute_expired"} and world.outbox_rows() == []


# ---- what the session writes is checked ----


def test_join_13_only_what_the_session_was_shown_may_be_cited_however_it_searched(world):
    task = world.look(KV)
    hidden = next(doc["id"] for doc in world.index.docs if doc["id"] not in shown(world, task))
    result = world.apply(task, world.contribution(task, doc_id=hidden))
    assert result["ok"] is False and any("was not shown" in error for error in result["errors"])

    task = world.look([(BOB, "那存储介质的发展呢")], root="")
    assert tasks.log_search(world.store, task["task_id"], "存储介质 HBF", [hidden], world.now)
    assert world.apply(task, world.contribution(task, doc_id=hidden))["outcome"] == "said"


def test_a_session_may_search_only_a_few_times_and_only_its_own_open_task(world):
    task = world.look(KV)
    for _ in range(SESSION_SEARCHES):
        assert tasks.log_search(world.store, task["task_id"], "查询", [], world.now)
    assert not tasks.log_search(world.store, task["task_id"], "再一次", [], world.now)
    assert tasks.searchable(world.store, "no-such-task") is None
    world.apply(task, world.contribution(task, act="none"))
    assert tasks.searchable(world.store, task["task_id"]) is None


def test_join_14_the_framing_must_answer_the_discussion_and_use_only_given_numbers(world):
    task = world.look(KV)
    quote = world.task_input(task)["messages"][0]["text"][:6]
    far = world.contribution(task, quote="这句原话并不在讨论里")
    assert world.apply(task, far)["errors"] == [
        "quote is not verbatim from the discussion: '这句原话并不在讨论里'",
        "quote is not verbatim: '这句原话并不在讨论里'",
    ]

    task = world.look([(ALICE, "首包延迟能降到 1.5 秒吗")])
    invented = world.contribution(task, framing="日报里有工作把它降到了 1.2 秒：")
    assert world.apply(task, invented)["errors"] == [
        "a number in the framing appears in no cited document nor in the discussion: 1.2"
    ]
    task = world.look([(ALICE, "首包延迟能降到 1.5 秒吗")])
    echoed = world.contribution(task, framing="你们说的 1.5 秒，日报里有一条相关的：")
    assert world.apply(task, echoed)["outcome"] == "said"


def test_it_does_not_repeat_what_it_already_said_in_a_discussion(world):
    first = world.look(KV)
    cited = world.task_input(first)["candidates"][0]["id"]
    world.apply(first, world.contribution(task=first, doc_id=cited))
    world.advance(THREAD_MIN_INTERVAL_SECONDS + 1)
    second = world.look([(BOB, "还有别的吗")], root=first["thread_key"].split(":", 1)[1])
    assert world.task_input(second)["already_said"][0]["id"] == cited
    result = world.apply(second, world.contribution(task=second, doc_id=cited))
    assert result["ok"] is False and any("already said" in error for error in result["errors"])


def test_invalid_output_is_final_and_ends_in_silence(world):
    task = world.look(KV)
    assert world.apply(task, {"schema_version": 1, "_task": {"task_id": task["task_id"], "kind": "contribute"}, "act": "add"})["ok"] is False
    assert world.store.fetchone("SELECT status FROM tasks WHERE task_id=?", (task["task_id"],))["status"] == "invalid"
    assert world.outbox_rows() == []


# ---- the owner ----


def test_join_08_a_coverage_gap_is_reported_to_the_owner_in_private_with_real_names(world):
    world.store.set_meta("report_to", OWNER)
    world.store.set_meta("member_names", {ALICE: "张三", BOB: "李四"})
    task = world.look([(ALICE, "我们在评估后端网络迁到超以太"), (BOB, "拥塞控制成熟吗")])
    assert world.apply(task, world.contribution(task, act="gap"))["outcome"] == "reported"
    world.flush()
    assert [row["kind"] for row in world.outbox_rows()] == ["report"]
    sent = world.transport.sent[-1]
    assert (sent["chat_id"], sent["reply_to"]) == ("oc_dm", "")
    opening = sent["text"].split("\n")[0]
    assert opening.startswith("群里在讨论一个日报没覆盖的方向（") and opening.endswith("，2 条消息，张三、李四）")
    assert "建议加的检索词：新检索词" in sent["text"] and "python briefing.py assistant report show gap-" in sent["text"]
    report = world.store.fetchone("SELECT * FROM reports")
    assert (report["kind"], report["status"]) == ("gap", "sent")
    assert world.reasons("reported") == {"gap:reported"}


def test_gap_reports_wait_for_an_owner_and_keep_within_a_daily_budget(world):
    def report(lines):
        task = world.look(lines)
        assert world.apply(task, world.contribution(task, act="gap"))["outcome"] == "reported"

    report([(ALICE, "我们在评估一个新方向")])
    assert world.store.fetchone("SELECT status FROM reports")["status"] == "recorded"  # nobody to tell yet
    assert world.outbox_rows() == []

    world.store.set_meta("report_to", OWNER)
    for index in range(REPORTS_PER_DAY):
        report([(ALICE, f"又一个没人覆盖的方向 {index}")])
    report([(ALICE, "第五个方向")])
    statuses = [row["status"] for row in world.store.fetchall("SELECT status FROM reports ORDER BY created_at")]
    assert statuses == ["recorded"] + ["queued"] * REPORTS_PER_DAY + ["recorded"]
    assert len(world.outbox_rows()) == REPORTS_PER_DAY


# ---- what stops it from speaking ----


def test_join_09_a_dislike_silences_that_thread_and_mute_or_off_silence_everything(world):
    said = world.speak([(ALICE, "KV cache 卸载怎么做"), (BOB, "有没有人做过分层卸载"), (ALICE, "CXL 内存池呢")])
    root = said["reply_to"]
    assert world.engine.on_reaction({"message_id": f"sent_{said['key']}", "emoji": "ThumbsDown", "operator_id": ALICE})["recorded"]
    world.advance(THREAD_MIN_INTERVAL_SECONDS + 1)
    world.discuss([(BOB, "再来一句")], root=root)
    world.advance(DEBOUNCE_SECONDS + 1)
    world.engine.sweep()
    assert world.reasons("ignored") == {"thread_muted"}

    policy = Policy.load(world.store)
    policy.muted_until = world.now + 600
    policy.save(world.store)
    world.new_topic()
    world.discuss([(ALICE, "静音期间的一句话")])
    world.advance(DEBOUNCE_SECONDS + 1)
    world.engine.sweep()
    assert world.reasons("ignored") == {"thread_muted", "muted"}

    world.policy(proactive="off")
    world.new_topic()
    assert world.say("关闭期间的一句话")["reason"] == "proactive_off"  # not even looked at
    assert world.tasks(kind="contribute") == []


def test_join_11_the_breaker_pauses_speaking_and_tells_the_owner(world):
    world.store.set_meta("report_to", OWNER)
    with world.store.transaction() as connection:
        for index in range(BREAKER_LIMIT):
            connection.execute(
                "INSERT INTO outbox(id, kind, chat_id, reply_to, thread_key, text, status, attempts, created_at, sent_at) VALUES(?, 'recommendation', ?, ?, ?, 'x', 'sent', 1, ?, ?)",
                (f"past-{index}", CHAT, f"om_old_{index}", f"{CHAT}:om_old_{index}", iso(world.now - 60), iso(world.now - 60)),
            )
    world.discuss(KV)
    world.advance(DEBOUNCE_SECONDS + 1)
    world.engine.sweep()
    assert world.tasks(kind="contribute") == [] and world.reasons("ignored") == {"breaker"}
    notice = world.store.fetchone("SELECT * FROM reports WHERE kind='notice'")
    assert notice["status"] == "queued" and json.loads(notice["body_json"])["text"].startswith("主动发言一小时超过了")
    assert world.say(CONFIDENT, mention=True)["decision"] == "answered"  # a mention is still answered


def test_below_the_breaker_nothing_is_paused(world):
    with world.store.transaction() as connection:
        for index in range(BREAKER_LIMIT - 1):
            connection.execute(
                "INSERT INTO outbox(id, kind, chat_id, reply_to, thread_key, text, status, attempts, created_at, sent_at) VALUES(?, 'recommendation', ?, ?, ?, 'x', 'sent', 1, ?, ?)",
                (f"past-{index}", CHAT, f"om_old_{index}", f"{CHAT}:om_old_{index}", iso(world.now - 60), iso(world.now - 60)),
            )
    assert world.look(KV)["kind"] == "contribute"


# ---- a new issue ----


def test_an_alert_offers_the_new_issue_beside_the_groups_discussions(world):
    world.discuss([(ALICE, "KV cache 卸载之后吞吐怎么样")])
    world.advance(DEBOUNCE_SECONDS + 1)
    world.engine.sweep()
    look = world.tasks(kind="contribute")[0]
    world.apply(look, world.contribution(look, act="none"))
    assert world.engine.queue_alert("2026-10-01", world.now) and not world.engine.queue_alert("2026-10-01", world.now)

    task = world.tasks(kind="alert")[0]
    payload = world.task_input(task)
    assert {item["id"] for item in payload["items"]} == {"item:" + "a" * 24, "item:" + "b" * 24}
    assert [message["text"] for message in payload["discussions"]] == ["KV cache 卸载之后吞吐怎么样"]
    outside = {"schema_version": 1, "_task": {"task_id": task["task_id"], "kind": "alert"},
               "picks": [{"doc_id": "radar:radar-1", "quote": "KV cache", "why": "不在这期里"}]}
    assert world.apply(task, outside)["errors"] == ["doc_id is not from this issue: radar:radar-1"]


def test_an_alert_is_one_message_with_what_the_session_picked(world):
    look = world.look([(ALICE, "KV cache 卸载之后吞吐怎么样")])
    world.apply(look, world.contribution(look, act="none"))
    world.engine.queue_alert("2026-10-01", world.now)
    task = world.tasks(kind="alert")[0]
    pick = {"doc_id": "item:" + "a" * 24, "quote": "KV cache 卸载", "why": "命中之后吞吐能提升，和你们问的对得上。"}
    assert world.apply(task, {"schema_version": 1, "_task": {"task_id": task["task_id"], "kind": "alert"}, "picks": [pick]})["outcome"] == "said"
    world.flush()
    sent = world.transport.sent[-1]
    assert (sent["kind"], sent["reply_to"], sent["chat_id"]) == ("alert", "", CHAT)
    lines = sent["text"].split("\n")
    assert lines[0] == "新一期日报（2026-10-01）里有 1 条和你们最近的讨论相关："
    assert lines[1] == "• 命中之后吞吐能提升，和你们问的对得上。"
    assert lines[2].startswith("  📄 **KV cache 分层卸载到内存与 SSD**（2026-10-01）：") and within_limit(sent["text"], "alert")


def test_nothing_relevant_in_a_new_issue_means_no_message(world):
    world.engine.queue_alert("2026-10-01", world.now)
    task = world.tasks(kind="alert")[0]
    quiet = {"schema_version": 1, "_task": {"task_id": task["task_id"], "kind": "alert"}, "picks": []}
    assert world.apply(task, quiet) == {"ok": True, "outcome": "silent", "picks": 0} and world.outbox_rows() == []


# ---- policy ----


def test_pol_01_the_version_follows_the_two_switches_and_every_decision_carries_it(world):
    default = Policy.load(world.store)
    assert (default.explicit, default.proactive) == (True, "auto")
    quiet = world.policy(explicit=False)
    assert len({default.version, quiet.version, world.policy(proactive="off").version}) == 3

    world.policy(explicit=False)
    task = world.look(KV)
    world.apply(task, world.contribution(task))
    assert {row["policy_version"] for row in world.store.fetchall("SELECT policy_version FROM decisions WHERE kind='contribute'")} == {quiet.version}


def test_pol_02_a_change_of_mode_voids_looks_in_flight_but_not_card_copy(world):
    look = world.look(KV)
    world.say("光交换机和 KV 卸载哪个更急", mention=True)
    feedback.prepare(world.root, world.config, world.state, world.store, "2026-10-20", world.now)
    world.policy(proactive="off")
    world.engine.sweep()
    statuses = {row["kind"]: row["status"] for row in world.store.fetchall("SELECT * FROM tasks")}
    assert statuses == {"contribute": "invalid", "refine": "invalid", "card_copy": "pending"}
    assert world.reasons("silent") == {"contribute_policy_changed"}


def test_pol_03_a_command_written_in_a_group_message_changes_nothing(world):
    before = Policy.load(world.store)
    world.say("assistant mode proactive off")
    world.say("assistant mute 1h", mention=True)
    world.flush()
    after = Policy.load(world.store)
    assert (after.version, after.muted_until) == (before.version, 0.0)


# ---- the gates on what leaves ----


def test_gate_01_a_reply_nobody_asked_for_is_refused_at_the_door(world):
    world.say("一个人发的普通消息")
    world.say(CONFIDENT, mention=True, sender="ou_other_bot", bot=True)
    queue(world, "answer:unaddressed", "answer", "om_1", "没人问的回答")
    queue(world, "answer:bot", "answer", "om_2", "回答机器人的")
    queue(world, "recommendation:unverified", "recommendation", "om_1", "没有决策的接话", thread_key=f"{CHAT}:om_1")
    queue(world, "report:orphan", "report", "", "没有记录的报告", chat_id="oc_dm")

    assert world.flush() == {"sent": 0, "retry": 0, "gone": 0, "failed": 0, "refused": 4}
    assert world.transport.calls == 0
    reasons = {row["id"]: row["last_error"] for row in world.outbox_rows()}
    assert reasons["answer:unaddressed"] == "The message being answered did not come from a person addressing the assistant"
    assert reasons["recommendation:unverified"] == "No accepted decision to speak covers this message"
    assert reasons["report:orphan"] == "No queued report covers this message"


def test_gate_01_a_contribution_is_held_once_the_mode_leaves_auto(world):
    task = world.look(KV)
    world.apply(task, world.contribution(task))
    world.policy(proactive="off")
    assert world.flush()["refused"] == 1
    assert world.transport.calls == 0 and world.outbox_rows()[0]["last_error"] == "Proactive mode is no longer auto"


def test_gate_02_a_long_reply_is_shortened_first_and_refused_when_it_cannot_fit(world):
    long_doc = {**world.index.get("item:" + "a" * 24), "lead": "这是一句很长的结论。" * 40}
    answer = compose_answer([{"doc": long_doc}], refined=True)
    assert within_limit(answer, "answer") and "[查看详情](" in answer
    assert answer.count("这是一句很长的结论") < 40  # the lead was cut at a sentence end

    queue(world, "answer:long", "answer", "om_1", "词" * 701)
    row = world.outbox_rows()[-1]
    assert (row["status"], row["last_error"]) == ("refused", "Exceeds the answer length limit: 701 characters")
    assert world.flush()["sent"] == 0 and world.transport.calls == 0


@pytest.mark.parametrize("field", ["framing", "quote"])
def test_gate_03_a_link_outside_the_index_is_rejected(world, field):
    task = world.look(KV)
    output = world.contribution(task)
    output[field] = "详见 https://arxiv.org/abs/2401.00001"
    result = world.apply(task, output)
    assert result["ok"] is False
    assert result["errors"][0] == "Output contains a link outside the index: https://arxiv.org/abs/2401.00001"
    assert world.outbox_rows() == []


def test_gate_04_and_05_a_mixed_day_leaves_only_answers_and_contributions_with_index_links_and_no_identity(world):
    world.say(CONFIDENT, mention=True)
    world.speak(KV)
    silent = world.look(SMALL_TALK)
    world.apply(silent, world.contribution(silent, act="none"))
    rows = world.outbox_rows()
    assert {row["kind"] for row in rows} == {"answer", "recommendation"} == set(outbox.ALLOWED_KINDS) - {"card", "alert", "report"}
    links = {url for row in rows for url in LINK.findall(row["text"])}
    assert links and links <= {doc["url"] for doc in world.index.docs}
    assert all(within_limit(row["text"], row["kind"]) for row in rows)
    with pytest.raises(outbox.OutboxError, match="not allowed"):
        queue(world, "progress", "progress", "om_1", "正在处理")
    for text in world.sent():
        assert re.search(r"[\u3400-\u9fff]", text)
        assert not re.search("我是|作为|助手|机器人|assistant|AI", text)
