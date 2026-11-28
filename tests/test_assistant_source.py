"""Replay tests for message intake, admission and answers (SRC, ADM, ANS)."""

import pytest

from assistant_support import ALICE, BOB, BOT, CHAT, OTHER_CHAT, SITE, World
from briefing_skill.assistant.backfill import backfill
from briefing_skill.assistant.constants import EXPLICIT_RATE_PER_MINUTE
from briefing_skill.assistant.replies import LOW_CONFIDENCE_HEADER, NO_MATCH_TEXT, NO_MATCH_UNREFINED_TEXT, within_limit

CONFIDENT = "KV cache 分层卸载怎么做"
UNCERTAIN = "光交换机和 KV 卸载哪个更急"
UNANSWERABLE = "zzqx vvwu jjkk"


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


# ---- Source ----


def test_src_01_own_messages_are_dropped(world):
    assert world.say("机器人自己的回答", sender=BOT)["decision"] == "dropped_own"
    assert world.store.fetchall("SELECT * FROM events") == []
    assert world.store.fetchall("SELECT * FROM dispositions") == []


def test_src_01_the_bots_own_card_read_back_from_history_is_dropped_too(world):
    world.store.execute(
        "INSERT INTO registry(message_id, idea_id, issue_date, pushed_at) VALUES('om_card', 'idea_c', '2026-10-01', '2026-10-06T10:00:00')"
    )
    # History shows the sender as the app, not as the bot's open_id.
    own = world.say("", sender="cli_app", bot=True, message_id="om_card")
    assert own["decision"] == "dropped_own" and world.store.fetchall("SELECT * FROM events") == []
    assert world.say("另一台机器人的消息", sender="cli_other_bot", bot=True)["reason"] == "bot"


def test_src_02_chats_outside_the_whitelist_are_blocked_and_keep_no_body(world):
    result = world.say(CONFIDENT, mention=True, chat=OTHER_CHAT)
    assert (result["decision"], result["reason"]) == ("blocked", "chat_not_whitelisted")
    assert world.outbox_rows() == []
    stored = world.store.fetchone("SELECT text FROM events WHERE message_id=?", (result["message_id"],))
    assert stored["text"] == ""


def test_src_03_three_ingress_paths_share_one_key(world):
    trigger = world.trigger(CONFIDENT, mention=True)
    assert world.engine.ingest(trigger)["decision"] == "answered"
    for via in ("backfill", "thread"):
        result = world.resend(trigger, via)
        assert (result["decision"], result["via"]) == ("duplicate", via)
    world.flush()
    assert len(world.transport.sent) == 1
    assert [row["via"] for row in world.store.fetchall("SELECT via FROM arrivals ORDER BY rowid")] == [
        "event", "backfill", "thread"
    ]
    assert len(world.store.fetchall("SELECT * FROM dispositions")) == 1


def test_src_04_a_redelivered_message_is_processed_once_and_not_revived_late(world):
    trigger = world.trigger(CONFIDENT, mention=True)
    world.engine.ingest(trigger)
    assert world.resend(trigger, "event")["decision"] == "duplicate"
    world.flush()
    assert len(world.transport.sent) == 1

    late = world.say(CONFIDENT, mention=True, at=world.now - 1801)
    assert (late["decision"], late["reason"]) == ("blocked", "stale")
    assert len(world.outbox_rows()) == 1


def test_src_05_a_reply_joins_its_root_thread(world):
    root = world.say("主频道的第一条")
    world.say("话题里的回复", root=root["message_id"])
    assert {row["thread_key"] for row in world.store.fetchall("SELECT thread_key FROM events")} == {
        f"{CHAT}:{root['message_id']}"
    }


def test_src_06_standalone_messages_cluster_by_time(world):
    first = world.say("第一条", advance=120)
    second = world.say("第二条", sender=BOB, advance=119)
    third = world.say("第三条", advance=480)
    fourth = world.say("第四条", sender=BOB)
    threads = {row["message_id"]: row["thread_key"] for row in world.store.fetchall("SELECT message_id, thread_key FROM events")}
    assert threads[first["message_id"]] == threads[second["message_id"]] == threads[third["message_id"]]
    assert threads[first["message_id"]] == f"{CHAT}:{first['message_id']}"
    assert threads[fourth["message_id"]] == f"{CHAT}:{fourth['message_id']}"


def test_src_07_every_message_keeps_one_disposition_with_a_reason(world):
    world.policy(proactive="off")
    sent = [
        world.say(CONFIDENT, mention=True),
        world.say(UNCERTAIN, mention=True),
        world.say("普通的一句闲聊"),
        world.say("机器人的消息", sender=BOT),
    ]
    rows = world.store.fetchall("SELECT * FROM dispositions")
    assert sorted(row["trigger_id"] for row in rows) == sorted(f"feishu:{item['message_id']}" for item in sent[:3])
    assert [row["decision"] for row in rows] == ["answered", "refine", "blocked"]
    assert [row["reason"] for row in rows] == ["confident", "uncertain", "proactive_off"]
    assert all(len(row["history_json"]) > 2 for row in rows)


def test_src_08_the_cursor_moves_only_after_a_successful_round(world):
    calls = []

    def reader(chat_id, start_ms):
        calls.append(start_ms)
        if len(calls) == 1:
            raise RuntimeError("history unavailable")
        return [world.trigger("补回来的消息", via="backfill", at=start_ms / 1000 + 6)] if len(calls) == 2 else []

    def cursor():
        return world.store.fetchone("SELECT cursor_ms FROM cursors WHERE chat_id=?", (CHAT,))["cursor_ms"]

    backfill(world.store, world.engine.ingest, reader, chat_id=CHAT, now=world.now)
    assert backfill(world.store, world.engine.ingest, reader, chat_id=CHAT, now=world.now)["failed"] is True
    assert cursor() == int(world.now * 1000)

    result = backfill(world.store, world.engine.ingest, reader, chat_id=CHAT, now=world.now)
    assert (result["failed"], result["ingested"]) == (False, 1)
    assert calls[1] == int(world.now * 1000) - 5000
    assert cursor() == int((calls[1] / 1000 + 6) * 1000)


def test_src_09_the_first_round_only_sets_the_cursor(world):
    calls = []
    result = backfill(
        world.store, world.engine.ingest, lambda chat, start: calls.append(start) or [], chat_id=CHAT, now=world.now
    )
    assert (result["first_round"], result["ingested"]) == (True, 0)
    assert calls == []
    assert world.store.fetchone("SELECT cursor_ms FROM cursors WHERE chat_id=?", (CHAT,))["cursor_ms"] == int(world.now * 1000)


# ---- Admission ----


@pytest.mark.parametrize("mode", ["off", "observe", "auto"])
def test_adm_01_a_mention_is_an_explicit_request_in_every_mode(world, mode):
    world.policy(proactive=mode)
    assert world.say(CONFIDENT, mention=True)["decision"] == "answered"


def test_adm_02_an_unaddressed_message_is_an_inferred_candidate(world):
    world.policy(proactive="observe")
    assert world.say("一句没有点名助手的消息") == {
        "message_id": "om_1", "decision": "pending", "reason": "awaiting_look"
    }


def test_adm_03_other_bots_are_not_admitted(world):
    result = world.say(CONFIDENT, mention=True, sender="ou_other_bot", bot=True)
    assert (result["decision"], result["reason"]) == ("blocked", "bot")
    assert world.outbox_rows() == []


def test_adm_04_admission_reads_metadata_not_the_body(world):
    world.policy(proactive="observe")
    unaddressed = [world.say("甲说的一句", sender=BOB), world.say("乙说的完全不同的一句", sender=BOB)]
    assert [(item["decision"], item["reason"]) for item in unaddressed] == [("pending", "awaiting_look")] * 2
    assert world.say(CONFIDENT, mention=True, sender=BOB)["decision"] == "answered"


def test_adm_05_off_mode_never_looks_at_discussions_but_still_answers(world):
    world.policy(proactive="off")
    assert world.say("没有点名的一句")["reason"] == "proactive_off"
    world.advance(60)
    world.engine.sweep()
    assert world.tasks() == []
    assert world.say(CONFIDENT, mention=True)["decision"] == "answered"


def test_adm_06_a_direct_message_is_answered_only_for_members(world):
    assert world.say(CONFIDENT, direct=True)["reason"] == "direct_non_member"
    world.store.set_meta("members", {CHAT: [ALICE]})
    assert world.say(CONFIDENT, direct=True)["decision"] == "answered"


def test_adm_07_a_mention_is_judged_by_the_mentions_field_not_the_text(world):
    world.policy(proactive="observe")
    assert world.say("@助手 请问 KV cache 分层卸载怎么做")["reason"] == "awaiting_look"
    assert world.say("@助手 " + CONFIDENT, mention=True)["decision"] == "answered"


# ---- Answers ----


def test_ans_02_an_answer_lists_published_items_with_links(world):
    world.say(CONFIDENT, mention=True)
    text = world.outbox_rows()[0]["text"]
    lines = text.split("\n")
    assert lines[0] == "日报库里相关的：" and lines[-1] == "觉得有用点 👍，不相关点 👎"
    bullets = [line for line in lines if line.startswith("• ")]
    assert 1 <= len(bullets) <= 3
    assert all("📄 **" in line and "：" in line and f"[查看详情]({SITE}" in line for line in bullets)
    assert within_limit(text)


def test_ans_03_nothing_relevant_gets_one_plain_sentence(world):
    world.say(UNANSWERABLE, mention=True)
    task = world.tasks(kind="refine")[0]
    assert world.task_input(task)["candidates"] == []
    assert world.apply(task, world.refinement(task, none=True))["outcome"] == "none_relevant"
    world.flush()
    assert world.sent() == [NO_MATCH_TEXT]


def test_ans_04_an_uncertain_question_is_refined_before_answering(world):
    assert world.say(UNCERTAIN, mention=True)["reason"] == "uncertain"
    assert world.outbox_rows() == []

    task = world.tasks(kind="refine")[0]
    chosen = world.task_input(task)["candidates"][0]
    assert world.apply(task, world.refinement(task, [chosen["id"]]))["outcome"] == "refined"
    assert world.store.fetchone("SELECT status FROM tasks WHERE task_id=?", (task["task_id"],))["status"] == "applied"
    world.flush()
    assert len(world.sent()) == 1 and chosen["title"] in world.sent()[0]
    row = world.outbox_rows()[0]
    assert (row["kind"], row["reply_to"], row["chat_id"]) == ("answer", "om_1", CHAT)


@pytest.mark.parametrize(
    "question, expected",
    [(UNCERTAIN, "日报库里相关度较低的有：（没能细查）"), (UNANSWERABLE, NO_MATCH_UNREFINED_TEXT)],
)
def test_ans_05_a_refinement_that_never_ran_falls_back_and_says_so(world, question, expected):
    world.say(question, mention=True)
    world.advance(601)
    world.engine.sweep()
    world.flush()
    assert len(world.sent()) == 1 and world.sent()[0].startswith(expected)
    assert world.sent()[0] != NO_MATCH_TEXT


def test_ans_06_each_mention_gets_at_most_one_reply(world):
    trigger = world.trigger(CONFIDENT, mention=True)
    world.engine.ingest(trigger)
    world.flush()
    assert world.resend(trigger, "backfill")["decision"] == "duplicate"
    world.flush()
    assert len(world.transport.sent) == 1


def test_ans_07_the_slow_path_stays_quiet_until_the_answer_is_ready(world):
    world.say(UNCERTAIN, mention=True)
    world.flush()
    world.advance(120)
    world.flush()
    assert world.transport.calls == 0

    task = world.tasks(kind="refine")[0]
    world.apply(task, world.refinement(task))
    world.flush()
    assert len(world.transport.sent) == 1


def test_ans_08_one_sender_is_limited_to_ten_questions_a_minute(world):
    results = [world.say(CONFIDENT, mention=True) for _ in range(EXPLICIT_RATE_PER_MINUTE + 5)]
    assert [result["decision"] for result in results] == ["answered"] * 10 + ["blocked"] * 5
    assert results[-1]["reason"] == "rate_limited"
    assert len(world.outbox_rows()) == 10


@pytest.mark.parametrize(
    "output",
    [
        {"selected": [{"doc_id": "item:" + "f" * 24, "quote": "KV"}]},
        {"queries": ["https://evil.example/paper"]},
    ],
    ids=["outside the candidates", "carries a link"],
)
def test_ans_10_an_invalid_refinement_is_rejected_and_falls_back(world, output):
    world.say(UNCERTAIN, mention=True)
    task = world.tasks(kind="refine")[0]
    result = world.apply(task, {**world.refinement(task), **output})
    assert result["ok"] is False and result["errors"]
    assert world.store.fetchone("SELECT status FROM tasks WHERE task_id=?", (task["task_id"],))["status"] == "invalid"
    world.flush()
    assert len(world.sent()) == 1 and "没能细查" in world.sent()[0]
    assert world.sent()[0].startswith(LOW_CONFIDENCE_HEADER)


def test_a_mention_inside_a_thread_is_answered_in_that_thread(world):
    root = world.say("主频道的第一条")
    world.say(CONFIDENT, mention=True, root=root["message_id"])
    world.flush()
    assert world.transport.sent[-1]["reply_to"] == "om_2"
    assert world.outbox_rows()[0]["thread_key"] == f"{CHAT}:{root['message_id']}"
