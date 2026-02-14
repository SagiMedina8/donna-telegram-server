import os
import json
import uuid
import requests
from flask import Flask, request

app = Flask(__name__)

# ---------- ENV ----------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_PEOPLE_DB_ID = os.environ.get("NOTION_PEOPLE_DB_ID", "")
NOTION_MEETINGS_DB_ID = os.environ.get("NOTION_MEETINGS_DB_ID", "")
NOTION_PROJECTS_DB_ID = os.environ.get("NOTION_PROJECTS_DB_ID", "")
NOTION_DONNA_INBOX_DB_ID = os.environ.get("NOTION_DONNA_INBOX_DB_ID", "")

TG_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
NOTION_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# ---------- In-memory state (MVP) ----------
PENDING = {}        # approval_id -> {"chat_id": int, "kind": str, "payload": dict}
SEEN_MESSAGES = set()  # (chat_id, message_id)

# ---------- Telegram helpers ----------
def tg(method: str, payload: dict):
    r = requests.post(f"{TG_BASE}/{method}", json=payload, timeout=20)
    r.raise_for_status()
    return r.json()

def send_message(chat_id: int, text: str, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    tg("sendMessage", payload)

def answer_callback_query(callback_query_id: str, text: str = ""):
    tg("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})

# ---------- Notion helpers ----------
def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

def notion_ready() -> bool:
    return bool(NOTION_TOKEN and NOTION_DONNA_INBOX_DB_ID)

def db_id_by_name(name: str) -> str:
    name = name.strip().lower()
    if name in ("people", "pepole", "persons", "person"):
        return NOTION_PEOPLE_DB_ID
    if name in ("meetings", "meeting"):
        return NOTION_MEETINGS_DB_ID
    if name in ("projects", "project"):
        return NOTION_PROJECTS_DB_ID
    if name in ("inbox", "donna", "donna-inbox", "donna_inbox"):
        return NOTION_DONNA_INBOX_DB_ID
    return ""

def notion_retrieve_database(database_id: str) -> dict:
    if not NOTION_TOKEN:
        raise RuntimeError("NOTION_TOKEN is missing")
    url = f"{NOTION_BASE}/databases/{database_id}"
    r = requests.get(url, headers=notion_headers(), timeout=20)
    r.raise_for_status()
    return r.json()

def notion_create_inbox_item(title: str, payload_text: str, status: str = "Executed"):
    """
    Creates a new page in Donna Inbox DB.
    Requires that Donna Inbox DB has at least:
      - Title (title)
    Optional if exist (we try to set, but won't fail if not):
      - Status (select)
      - Payload (rich_text or text)
    """
    if not notion_ready():
        raise RuntimeError("Notion is not configured (NOTION_TOKEN / NOTION_DONNA_INBOX_DB_ID)")

    props = {
        "Title": {
            "title": [{"type": "text", "text": {"content": title}}]
        }
    }

    # Try to set common optional fields (only if exist in DB schema)
    # We'll retrieve schema once per call for safety (MVP)
    schema = notion_retrieve_database(NOTION_DONNA_INBOX_DB_ID)
    properties = schema.get("properties", {})

    if "Status" in properties and properties["Status"].get("type") == "select":
        props["Status"] = {"select": {"name": status}}

    if "Payload" in properties:
        ptype = properties["Payload"].get("type")
        if ptype in ("rich_text", "text"):
            props["Payload"] = {"rich_text": [{"type": "text", "text": {"content": payload_text}}]}

    body = {
        "parent": {"database_id": NOTION_DONNA_INBOX_DB_ID},
        "properties": props
    }

    r = requests.post(f"{NOTION_BASE}/pages", headers=notion_headers(), json=body, timeout=20)
    r.raise_for_status()
    return r.json()

# ---------- Core webhook ----------
@app.post("/telegram")
def telegram_webhook():
    update = request.get_json(silent=True) or {}

    # A) Button clicks (Approve/Reject)
    if "callback_query" in update:
        cq = update["callback_query"]
        data = cq.get("data", "")
        chat_id = cq["message"]["chat"]["id"]
        callback_id = cq["id"]

        if ":" not in data:
            answer_callback_query(callback_id, "משהו השתבש")
            return {"ok": True}

        action, approval_id = data.split(":", 1)
        item = PENDING.pop(approval_id, None)

        if not item:
            answer_callback_query(callback_id, "הבקשה כבר טופלה/לא נמצאה")
            send_message(chat_id, "הבקשה כבר טופלה או לא נמצאה.")
            return {"ok": True}

        if action == "reject":
            answer_callback_query(callback_id, "נדחה")
            send_message(chat_id, "נדחה ❌")
            return {"ok": True}

        # Approve:
        answer_callback_query(callback_id, "אושר")

        kind = item.get("kind")
        payload = item.get("payload", {})

        try:
            if kind == "inbox_create":
                title = payload.get("title", "Donna Inbox item")
                text = payload.get("text", "")
                notion_create_inbox_item(title=title, payload_text=text, status="Executed")
                send_message(chat_id, "אושר ✅\nכתבתי ל-Notion (Donna Inbox).")
            else:
                send_message(chat_id, "אושר ✅\n(אבל אין פעולה מחוברת עדיין)")
        except Exception as e:
            send_message(chat_id, f"שגיאה בכתיבה ל-Notion:\n{str(e)}")

        return {"ok": True}

    # B) Normal messages
    msg = update.get("message")
    if not msg:
        return {"ok": True}

    chat_id = msg["chat"]["id"]
    message_id = msg.get("message_id")

    # Dedup (avoid duplicates on retries)
    key = (chat_id, message_id)
    if message_id is not None:
        if key in SEEN_MESSAGES:
            return {"ok": True}
        SEEN_MESSAGES.add(key)
        if len(SEEN_MESSAGES) > 2000:
            SEEN_MESSAGES.clear()

    text = (msg.get("text") or "").strip()

    # ---- Commands ----
    # 1) /schema <people|meetings|projects|inbox>
    if text.lower().startswith("/schema"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(chat_id, "שימוש:\n/schema people|meetings|projects|inbox")
            return {"ok": True}

        target = parts[1].strip()
        database_id = db_id_by_name(target)
        if not database_id:
            send_message(chat_id, "לא זיהיתי DB. נסה:\n/schema people\n/schema meetings\n/schema projects\n/schema inbox")
            return {"ok": True}

        if not NOTION_TOKEN:
            send_message(chat_id, "חסר NOTION_TOKEN ב-Render Environment Variables.")
            return {"ok": True}

        try:
            db = notion_retrieve_database(database_id)
            props = db.get("properties", {})
            lines = []
            for name, meta in props.items():
                lines.append(f"- {name}: {meta.get('type')}")
            send_message(chat_id, "Schema:\n" + "\n".join(lines[:60]))
            if len(lines) > 60:
                send_message(chat_id, f"(הצגתי 60 ראשונים מתוך {len(lines)})")
        except Exception as e:
            send_message(chat_id, f"שגיאה בשליפת schema:\n{str(e)}")

        return {"ok": True}

    # 2) /inbox <free text>  -> propose -> approve -> write to Notion Inbox
    if text.lower().startswith("/inbox"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(chat_id, "שימוש:\n/inbox <טקסט חופשי>\nדוגמה:\n/inbox סיכום פגישה עם יואב על Open Banking")
            return {"ok": True}

        if not notion_ready():
            send_message(chat_id, "Notion לא מוגדר עדיין.\nוודא שהגדרת ב-Render:\nNOTION_TOKEN + NOTION_DONNA_INBOX_DB_ID")
            return {"ok": True}

        free_text = parts[1].strip()
        approval_id = str(uuid.uuid4())[:8]

        PENDING[approval_id] = {
            "chat_id": chat_id,
            "kind": "inbox_create",
            "payload": {
                "title": "Donna Inbox",
                "text": free_text
            }
        }

        send_message(
            chat_id,
            "דונה מבקשת אישור לכתוב ל-Notion (Donna Inbox):\n" + free_text,
            reply_markup={
                "inline_keyboard": [
                    [
                        {"text": "אשר", "callback_data": f"approve:{approval_id}"},
                        {"text": "דחה", "callback_data": f"reject:{approval_id}"},
                    ]
                ]
            }
        )
        return {"ok": True}

    # Existing demo
    if text == "/approve_demo":
        approval_id = str(uuid.uuid4())[:8]
        action_text = "דמו אישור: פעולה שלא עושה כלום"

        PENDING[approval_id] = {"chat_id": chat_id, "kind": "demo", "payload": {"text": action_text}}

        send_message(
            chat_id,
            f"דונה מבקשת אישור:\n{action_text}",
            reply_markup={
                "inline_keyboard": [
                    [
                        {"text": "אשר", "callback_data": f"approve:{approval_id}"},
                        {"text": "דחה", "callback_data": f"reject:{approval_id}"},
                    ]
                ]
            },
        )
        return {"ok": True}

    # Default
    send_message(chat_id, "קיבלתי.\nפקודות זמינות:\n/schema people|meetings|projects|inbox\n/inbox <טקסט>\n/approve_demo")
    return {"ok": True}

@app.get("/")
def health():
    return "OK"
