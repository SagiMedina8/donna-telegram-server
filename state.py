"""
Donna Agent — State
In-memory state for MVP.
"""
import time

# Pending approvals
PENDING = {}

# Deduplication
SEEN = set()
MAX_SEEN = 2000

# Expand data
EXPAND = {}

# Conversation context per chat: chat_id -> {"topic": str, "entity": str, "ts": float}
CONTEXT = {}

# Meetings we already sent followup for today: set of page_ids
FOLLOWED_UP = set()
FOLLOWED_UP_DATE = ""  # resets daily


def is_duplicate(chat_id: int, message_id: int | None) -> bool:
    if message_id is None:
        return False
    key = (chat_id, message_id)
    if key in SEEN:
        return True
    SEEN.add(key)
    if len(SEEN) > MAX_SEEN:
        SEEN.clear()
    return False


def set_context(chat_id: int, topic: str, entity: str = ""):
    CONTEXT[chat_id] = {"topic": topic, "entity": entity, "ts": time.time()}


def get_context(chat_id: int) -> dict | None:
    ctx = CONTEXT.get(chat_id)
    if not ctx:
        return None
    # Context expires after 5 minutes
    if time.time() - ctx["ts"] > 300:
        CONTEXT.pop(chat_id, None)
        return None
    return ctx


def mark_followed_up(page_id: str, today: str):
    global FOLLOWED_UP_DATE
    if FOLLOWED_UP_DATE != today:
        FOLLOWED_UP.clear()
        FOLLOWED_UP_DATE = today
    FOLLOWED_UP.add(page_id)


def was_followed_up(page_id: str) -> bool:
    return page_id in FOLLOWED_UP
