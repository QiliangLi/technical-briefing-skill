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

# Self-check and retention.
RETENTION_DAYS = 30
DISLIKE_PAUSE_RATIO = 0.5
DISLIKE_PAUSE_MIN_SAMPLES = 4

EMOJI_THUMBS_UP = "THUMBSUP"
EMOJI_THUMBS_DOWN = "ThumbsDown"
