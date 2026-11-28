"""Fixed limits for the Feishu group assistant.

These are code constants on purpose. The design keeps settings few: a value becomes
configuration only after a trial shows it needs tuning per deployment.
"""

# Shape gate for a proactive recommendation.
SHAPE_MIN_MESSAGES = 3
SHAPE_MIN_SENDERS = 2
QUIET_SECONDS = 90
CLUSTER_WINDOW_SECONDS = 600
CLUSTER_MAX_GAP_SECONDS = 300
THREAD_COOLDOWN_SECONDS = 24 * 3600
OBSERVE_COOLDOWN_SECONDS = 30 * 60
DAILY_PROACTIVE_CAP = 3
ANCHORED_MIN_MESSAGES = 1

# Explicit answers.
EXPLICIT_RATE_PER_MINUTE = 10
ANSWER_MAX_ITEMS = 3

# Replies. Cards follow a template and are not counted against the word limit.
IM_WORD_LIMIT = 100
ROADMAP_PER_ANSWER = 1
OUTBOX_MAX_ATTEMPTS = 5

# Semantic tasks.
REFINE_TTL_SECONDS = 600
ASSESS_TTL_SECONDS = 300
TASK_BATCH_MIN_AGE_SECONDS = 60
TASK_BATCH_MAX = 5
DAILY_WAKE_CAP = 40
REFINE_CANDIDATES = 20
ASSESS_CANDIDATES = 10
WINDOW_MAX_MESSAGES = 20
MESSAGE_CHAR_LIMIT = 400
CONTEXT_NEIGHBOURS = 5

# Intake. A message first seen this long after it was written is recorded but
# not answered: the platform redelivers what was missed while the machine slept.
STALE_SECONDS = 30 * 60
BACKFILL_INTERVAL_SECONDS = 60
BACKFILL_REWIND_SECONDS = 5
SWEEP_INTERVAL_SECONDS = 5
CONSUMER_READY_TIMEOUT_SECONDS = 45
CONSUMER_MIN_STABLE_SECONDS = 60
CONSUMER_MAX_BACKOFF_SECONDS = 60
BACKFILL_MAX_ROUNDS_PER_TICK = 4
# A chat's history lists a thread's root but not its replies, so the threads
# active in the last week are polled every third backfill round.
THREAD_POLL_EVERY = 3
THREAD_POLL_MAX = 10
THREAD_POLL_WINDOW_SECONDS = 7 * 24 * 3600

# The resident process.
SERVICE_TICK_SECONDS = 1
STOP_TIMEOUT_SECONDS = 30
INDEX_CHECK_INTERVAL_SECONDS = 3600

# Self-check and retention.
RETENTION_DAYS = 30
DISLIKE_PAUSE_RATIO = 0.5
DISLIKE_PAUSE_MIN_SAMPLES = 4

EMOJI_THUMBS_UP = "THUMBSUP"
EMOJI_THUMBS_DOWN = "ThumbsDown"
# On a reply a reaction grades retrieval; on a card it is one of the four verdicts.
# Feishu has no reaction emoji for the other two, so they exist only as buttons.
REPLY_REACTIONS = {EMOJI_THUMBS_UP: "up", EMOJI_THUMBS_DOWN: "down"}
CARD_REACTIONS = {EMOJI_THUMBS_UP: "worth_validating", EMOJI_THUMBS_DOWN: "not_promising"}
CARD_CHOICES = {
    "worth_validating": "值得投入验证",
    "not_promising": "不看好",
    "insufficient_evidence": "证据不足",
    "prior_art_exists": "已有人做过",
}

# Idea cards. A card is the one message nobody asked for in the moment, so it
# goes out only through an explicit confirmation and at most once a week.
CARDS_PER_PUSH = 3
PUSH_INTERVAL_DAYS = 7
# An idea nobody answered is shown again only this long after its last showing.
REVIVE_AFTER_DAYS = 28
