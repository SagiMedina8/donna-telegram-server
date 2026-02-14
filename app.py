import os
import json
import uuid
import requests
from flask import Flask, request
from datetime import datetime, timezone

app = Flask(__name__)

# ---------- ENV ----------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_PEOPLE_DB_ID = os.environ.get("NOTION_PEOPLE_DB_ID", "")
NOTION_MEETINGS_DB_ID = os.environ.get("NOTION_MEETINGS_DB_ID", "")
NOTION_PROJECTS_DB_ID = os.environ.get("NOTION_PROJECTS_DB_ID", "")
NOTION_DONNA_INBOX_DB_ID = os.environ.get("NOTION_DONNA_INBOX_DB_ID", "")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1")  # cost-friendly default

TG_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
NOTION_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
OPENAI_BASE = "https://api.openai.com/v1"

# ---------- In-memory state (MVP) ----------
PENDING = {}  # approval_id -> {"chat_id": int, "kind": str, "payload": dict}
SEEN_MESSAGES = set()  # (chat_id, message_id)

# ---------- Telegram helpers ----------
def tg(method: str, payload: dict):
    r = requests.post(f"{TG_BASE}/{method}", json=payload, timeout=30)
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

def notion_ready_people() -> bool:
    return bool(NOTION_TOKEN and NOTION_PEOPLE_DB_ID)

def notion_retrieve_database(database_id: str) -> dict:
    url = f"{NOTION_BASE}/databases/{database_id}"
    r = requests.get(url, headers=notion_headers(), timeout=30)
    r.raise_for_status()
    return r.json()

def notion_query_people_by_name(name: str, limit: int = 10) -> list:
    """
    Query People DB by title property "שם" (contains).
    Returns list of page objects.
    """
    url = f"{NOTION_BASE}/databases/{NOTION_PEOPLE_DB_ID}/query"
    body = {
        "page_size": limit,
        "filter": {
            "property": "שם",
            "title": {"contains": name}
        }
    }
    r = requests.post(url, headers=notion_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])

def notion_get_page(page_id: str) -> dict:
    url = f"{NOTION_BASE}/pages/{page_id}"
    r = requests.get(url, headers=notion_headers(), timeout=30)
    r.raise_for_status()
    return r.json()

def _extract_rich_text(page: dict, prop_name: str) -> str:
    props = page.get("properties", {})
    prop = props.get(prop_name, {})
    ptype = prop.get("type")
    if ptype == "rich_text":
        arr = prop.get("rich_text", [])
        return "".join([x.get("plain_text", "") for x in arr])
    if ptype == "title":
        arr = prop.get("title", [])
        return "".join([x.get("plain_text", "") for x in arr])
    return ""

def notion_update_rich_text(page_id: str, prop_name: str, new_text: str):
    url = f"{NOTION_BASE}/pages/{page_id}"
    body = {
        "properties": {
            prop_name: {
                "rich_text": [{"type": "text", "text": {"content": new_text}}]
            }
        }
    }
    r = requests.patch(url, headers=notion_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json()

# ---------- OpenAI helpers (Responses API) ----------
def openai_headers():
    return {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

def openai_ready() -> bool:
    return bool(OPENAI_API_KEY)

# Allowed People fields (based on your schema; keep tight for safety)
ALLOWED_PEOPLE_FIELDS = [
    "טיפים להכנה",
    "הערות אישיות",
    "תחביבים ותחומי עניין",
    "אופן עבודה מועדף",
    "תחום",
    "תפקיד",
    "מחלקה",
    "לייבלים",
    "פעיל",
]



def llm_digest_to_plan(user_text: str) -> dict:
    schema = {
        "name": "DonnaDigestPlan",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "questions": {"type": "array", "items": {"type": "string"}},
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "person_name": {"type": "string"},
                            "field": {"type": "string", "enum": ALLOWED_PEOPLE_FIELDS},
                            "op": {"type": "string", "enum": ["append", "set"]},
                            "value": {"type": "string"},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "why": {"type": "string"},
                        },
                        "required": ["person_name", "field", "op", "value", "confidence", "why"],
                    },
                },
            },
            "required": ["questions", "updates"],
        },
    }

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M (%A) %Z")

    system = (
        f"Current local time: {now}\n"
        "אתה Donna, עוזר/ת תפעולי/ת שמסיק/ה מתוכן חופשי תכנית עדכונים לדאטהבייס People ב-Notion.\n"
        "כל פלט חייב להיות JSON תקין לפי הסכימה בלבד.\n"
        "כללים:\n"
        "1) אם אין מספיק מידע לזהות אדם/עדכון בביטחון – הוסף שאלה ב-questions במקום להמציא.\n"
        "2) אל תציע עדכון לשדות שלא ברשימת השדות המותרים.\n"
        "3) העדכונים צריכים להיות קטנים ומעשיים.\n"
        "4) confidence: 0-1. אם מתחת ל-0.6, העדף לשאול שאלה במקום להציע עדכון.\n"
    )

    body = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        # Structured Outputs in Responses API:
        "text": {
            "format": {
                "type": "json_schema",
                "name": "DonnaDigestPlan",
                "schema": schema["schema"],
                "strict": True
            }
        },

        "max_output_tokens": 700,
    }

    r = requests.post(f"{OPENAI_BASE}/responses", headers=openai_headers(), json=body, timeout=60)
    r.raise_for_status()
    data = r.json()

    # Recommended convenience field if present:
    out = data.get("output_text")
    if out:
        return json.loads(out)

    # Fallback: walk output array
    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text" and "text" in c:
                return json.loads(c["text"])

    raise RuntimeError("OpenAI response had no parsable JSON text")


# ---------- Commands ----------
def cmd_schema(chat_id: int, target: str):
    target = target.strip().lower()
    if not NOTION_TOKEN:
        send_message(chat_id, "חסר NOTION_TOKEN ב-Render Environment Variables.")
        return

    # We only need schema for people right now, but keep it generic
    mapping = {
        "people": NOTION_PEOPLE_DB_ID,
        "meetings": NOTION_MEETINGS_DB_ID,
        "projects": NOTION_PROJECTS_DB_ID,
        "inbox": NOTION_DONNA_INBOX_DB_ID,
    }
    db_id = mapping.get(target, "")
    if not db_id:
        send_message(chat_id, "שימוש:\n/schema people|meetings|projects|inbox")
        return

    try:
        db = notion_retrieve_database(db_id)
        props = db.get("properties", {})
        lines = [f"- {name}: {meta.get('type')}" for name, meta in props.items()]
        send_message(chat_id, "Schema:\n" + "\n".join(lines[:60]))
        if len(lines) > 60:
            send_message(chat_id, f"(הצגתי 60 ראשונים מתוך {len(lines)})")
    except Exception as e:
        send_message(chat_id, f"שגיאה בשליפת schema:\n{str(e)}")

def propose_people_update(chat_id: int, person_name: str, field: str, op: str, value: str, why: str):
    """
    Finds the person in Notion and proposes a single update with approval.
    """
    if not notion_ready_people():
        send_message(chat_id, "Notion People לא מוגדר.\nוודא: NOTION_TOKEN + NOTION_PEOPLE_DB_ID")
        return

    matches = notion_query_people_by_name(person_name, limit=10)
    if len(matches) == 0:
        send_message(chat_id, f"לא מצאתי אדם בשם שמכיל: '{person_name}'.\nאפשר לנסות שם מלא יותר.")
        return

    if len(matches) > 1:
        # MVP: avoid wrong person. Ask user to refine.
        names = []
        for p in matches[:5]:
            title = _extract_rich_text(p, "שם")
            role = _extract_rich_text(p, "תפקיד")
            dept = _extract_rich_text(p, "מחלקה")
            hint = " | ".join([x for x in [title, role, dept] if x])
            names.append(f"- {hint}")
        send_message(
            chat_id,
            "מצאתי כמה התאמות. כדי שלא אעדכן את האדם הלא נכון, תכתוב שם מדויק יותר:\n" + "\n".join(names)
        )
        return

    page = matches[0]
    page_id = page["id"]
    page_title = _extract_rich_text(page, "שם") or person_name

    # Build preview (what will change)
    try:
        full_page = notion_get_page(page_id)
        current = _extract_rich_text(full_page, field) if op == "append" else _extract_rich_text(full_page, field)
        if op == "append":
            new_text = (current + ("\n" if current.strip() else "") + value).strip()
            preview = f"נוכחי:\n{current or '(ריק)'}\n\nחדש:\n{new_text}"
        else:
            new_text = value.strip()
            preview = f"נוכחי:\n{current or '(ריק)'}\n\nחדש:\n{new_text}"
    except Exception:
        # If reading fails, still allow proposing but without preview
        new_text = value.strip()
        preview = "(לא הצלחתי לקרוא ערך נוכחי לצורך תצוגה מקדימה)"

    approval_id = str(uuid.uuid4())[:8]
    PENDING[approval_id] = {
        "chat_id": chat_id,
        "kind": "people_update",
        "payload": {
            "page_id": page_id,
            "page_title": page_title,
            "field": field,
            "op": op,
            "value": value,
            "new_text": new_text
        }
    }

    msg = (
        f"דונה מציעה עדכון ב-People:\n"
        f"אדם: {page_title}\n"
        f"שדה: {field}\n"
        f"פעולה: {op}\n"
        f"סיבה: {why}\n\n"
        f"תצוגה מקדימה:\n{preview}\n\n"
        f"לאשר?"
    )

    send_message(
        chat_id,
        msg,
        reply_markup={
            "inline_keyboard": [
                [
                    {"text": "אשר", "callback_data": f"approve:{approval_id}"},
                    {"text": "דחה", "callback_data": f"reject:{approval_id}"},
                ]
            ]
        },
    )

# ---------- Core webhook ----------
@app.post("/telegram")
def telegram_webhook():
    update = request.get_json(silent=True) or {}

    # A) Button clicks
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

        # approve
        answer_callback_query(callback_id, "אושר")

        kind = item.get("kind")
        payload = item.get("payload", {})

        try:
            if kind == "people_update":
                page_id = payload["page_id"]
                field = payload["field"]
                new_text = payload["new_text"]
                notion_update_rich_text(page_id, field, new_text)
                send_message(chat_id, f"אושר ✅\nעדכנתי ב-Notion: {payload.get('page_title','')}\nשדה: {field}")
            else:
                send_message(chat_id, "אושר ✅\n(אין פעולה מחוברת)")
        except Exception as e:
            send_message(chat_id, f"שגיאה בביצוע:\n{str(e)}")

        return {"ok": True}

    # B) Normal messages
    msg = update.get("message")
    if not msg:
        return {"ok": True}

    chat_id = msg["chat"]["id"]
    message_id = msg.get("message_id")

    # Dedup
    key = (chat_id, message_id)
    if message_id is not None:
        if key in SEEN_MESSAGES:
            return {"ok": True}
        SEEN_MESSAGES.add(key)
        if len(SEEN_MESSAGES) > 2000:
            SEEN_MESSAGES.clear()

    text = (msg.get("text") or "").strip()

    # /schema
    if text.lower().startswith("/schema"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(chat_id, "שימוש:\n/schema people|meetings|projects|inbox")
            return {"ok": True}
        cmd_schema(chat_id, parts[1])
        return {"ok": True}

    # /digest <free text>
    if text.lower().startswith("/digest"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(chat_id, "שימוש:\n/digest <טקסט חופשי>\nדוגמה:\n/digest סיכום פגישה עם יואב: אוהב שחמט, מעדיף הודעות קצרות...")
            return {"ok": True}

        if not openai_ready():
            send_message(chat_id, "חסר OPENAI_API_KEY ב-Render Environment Variables.")
            return {"ok": True}

        if not notion_ready_people():
            send_message(chat_id, "Notion People לא מוגדר.\nוודא: NOTION_TOKEN + NOTION_PEOPLE_DB_ID")
            return {"ok": True}

        user_text = parts[1].strip()

        try:
            plan = llm_digest_to_plan(user_text)
        except Exception as e:
            send_message(chat_id, f"שגיאה בקריאה ל-LLM:\n{str(e)}")
            return {"ok": True}

        questions = plan.get("questions", [])
        updates = plan.get("updates", [])

        if questions:
            # ask questions first (MVP)
            send_message(chat_id, "יש לי שאלות הבהרה לפני עדכון:\n- " + "\n- ".join(questions))
            # still show updates if any, but only high confidence
        high_updates = [u for u in updates if float(u.get("confidence", 0)) >= 0.6]

        if not high_updates:
            send_message(chat_id, "לא מצאתי עדכון מספיק בטוח לבצע כרגע. אם תרצה, נסה לכתוב שם מלא יותר + פרט אחד ברור.")
            return {"ok": True}

        # MVP: propose first update only (keeps UX simple & cost low)
        u = high_updates[0]
        propose_people_update(
            chat_id=chat_id,
            person_name=u["person_name"],
            field=u["field"],
            op=u["op"],
            value=u["value"],
            why=u["why"],
        )
        if len(high_updates) > 1:
            send_message(chat_id, f"(מצאתי עוד {len(high_updates)-1} עדכונים אפשריים. נטפל בהם אחד-אחד אחרי שתאשר/תדחה.)")
        return {"ok": True}

    # Default help
    send_message(chat_id, "קיבלתי.\nפקודות:\n/schema people|meetings|projects|inbox\n/digest <טקסט חופשי>")
    return {"ok": True}

@app.get("/")
def health():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
