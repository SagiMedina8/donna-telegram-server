"""
Donna Agent — State
In-memory state for MVP.
"""
import time

# Pending approvals: approval_id -> {chat_id, kind, payload}
PENDING = {}

# Deduplication: set of (chat_id, message_id)
SEEN = set()
MAX_SEEN = 2000

# Expand data: expand_id -> {page_id, db}
EXPAND = {}

# Conversation context: chat_id -> {topic, entity, ts, extra}
CONTEXT = {}

# Creation flow: chat_id -> {type, data, missing, step}
CREATION = {}

# Meetings already followed-up today: set of page_ids
FOLLOWED_UP = set()
FOLLOWED_UP_DATE = ""


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


# ── Context ──

def set_context(chat_id: int, topic: str, entity: str = "", extra: dict | None = None):
    CONTEXT[chat_id] = {"topic": topic, "entity": entity, "ts": time.time(), "extra": extra or {}}


def get_context(chat_id: int) -> dict | None:
    ctx = CONTEXT.get(chat_id)
    if not ctx:
        return None
    if time.time() - ctx["ts"] > 300:  # 5 min expiry
        CONTEXT.pop(chat_id, None)
        return None
    return ctx


def clear_context(chat_id: int):
    CONTEXT.pop(chat_id, None)


# ── Creation flow ──

def start_creation(chat_id: int, ctype: str, data: dict, missing: list):
    CREATION[chat_id] = {"type": ctype, "data": data, "missing": missing, "step": 0}


def get_creation(chat_id: int) -> dict | None:
    return CREATION.get(chat_id)


def advance_creation(chat_id: int, field: str, value: str):
    flow = CREATION.get(chat_id)
    if flow:
        flow["data"][field] = value
        if field in flow["missing"]:
            flow["missing"].remove(field)
        flow["step"] += 1


def end_creation(chat_id: int):
    CREATION.pop(chat_id, None)


# ── Followup tracking ──

def mark_followed_up(page_id: str, today: str):
    global FOLLOWED_UP_DATE
    if FOLLOWED_UP_DATE != today:
        FOLLOWED_UP.clear()
        FOLLOWED_UP_DATE = today
    FOLLOWED_UP.add(page_id)


def was_followed_up(page_id: str) -> bool:
    return page_id in FOLLOWED_UP
