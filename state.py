"""
Donna Agent — State
In-memory state for MVP. Will move to persistent storage later.
"""

# Pending approvals: approval_id -> {"chat_id": int, "kind": str, "payload": dict}
PENDING = {}

# Deduplication: set of (chat_id, message_id)
SEEN = set()

# Selections waiting for user pick: chat_id -> {"items": [...], "context": str}
SELECTIONS = {}

# Expand data: expand_id -> {"page_id": str, "db": str}
EXPAND = {}

MAX_SEEN = 2000


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
