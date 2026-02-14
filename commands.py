"""
Donna Agent — Commands
All command handlers mapped to Hebrew commands.
"""
import uuid
import notion_client as notion
import telegram_client as tg_client
import formatters as fmt
import state
from llm import digest_to_plan
from config import (
    NOTION_TOKEN, OPENAI_API_KEY,
    NOTION_PEOPLE_DB_ID, NOTION_MEETINGS_DB_ID,
    NOTION_PROJECTS_DB_ID, NOTION_DONNA_INBOX_DB_ID,
    DB_NAME_MAP,
)


# ═══════════════════════════════════════════════════
#  RETRIEVAL COMMANDS (קריאה)
# ═══════════════════════════════════════════════════

def cmd_who(chat_id: int, name: str):
    """
    /מי <שם> — חיפוש אדם והצגת כרטיס.
    If multiple matches: numbered list for selection.
    If one: short card with expand button.
    """
    if not name.strip():
        tg_client.send(chat_id, "שימוש: /מי <שם>\nדוגמה: /מי אלירן")
        return

    try:
        matches = notion.query_people(name.strip(), limit=10)
    except Exception as e:
        tg_client.send(chat_id, f"שגיאה בחיפוש: {e}")
        return

    if not matches:
        tg_client.send(chat_id, f"לא מצאתי אף אדם בשם '{name}'.")
        return

    if len(matches) == 1:
        _show_person_card(chat_id, matches[0])
        return

    # Multiple matches — show numbered list
    items = []
    for i, page in enumerate(matches[:10]):
        card = notion.get_person_card(page, full=False)
        label = fmt.format_person_list_item(card)
        expand_id = str(uuid.uuid4())[:8]
        state.EXPAND[expand_id] = {"page_id": page["id"], "db": "people"}
        items.append({"label": label, "callback_data": f"expand_person:{expand_id}"})

    tg_client.send_selection(chat_id, f"מצאתי {len(matches)} תוצאות:", items)


def _show_person_card(chat_id: int, page: dict):
    """Show short person card with expand button."""
    card = notion.get_person_card(page, full=False)
    text = fmt.format_person_short(card)
    expand_id = str(uuid.uuid4())[:8]
    state.EXPAND[expand_id] = {"page_id": page["id"], "db": "people"}
    tg_client.send_with_expand(chat_id, text, f"expand_person:{expand_id}")


def cmd_today(chat_id: int):
    """/היום — פגישות היום."""
    _show_meetings_for_date(chat_id, notion.today_str(), "היום")


def cmd_tomorrow(chat_id: int):
    """/מחר — פגישות מחר."""
    _show_meetings_for_date(chat_id, notion.tomorrow_str(), "מחר")


def _show_meetings_for_date(chat_id: int, date_str: str, label: str):
    try:
        meetings = notion.query_meetings_by_date(date_str)
    except Exception as e:
        tg_client.send(chat_id, f"שגיאה בשליפת פגישות: {e}")
        return

    if not meetings:
        tg_client.send(chat_id, f"אין פגישות ל{label} ({date_str}).")
        return

    # Build list with expand buttons
    cards = []
    items = []
    for page in meetings:
        card = notion.get_meeting_card(page, full=False)
        cards.append(card)
        expand_id = str(uuid.uuid4())[:8]
        state.EXPAND[expand_id] = {"page_id": page["id"], "db": "meetings"}
        items.append({
            "label": fmt.format_meeting_short(card).replace("\n", " · "),
            "callback_data": f"expand_meeting:{expand_id}",
        })

    header = f"<b>📅 פגישות {label} ({date_str}):</b>"
    meeting_list = fmt.format_meetings_list(cards)
    text = f"{header}\n\n{meeting_list}"

    # Add expand buttons for each meeting
    buttons = []
    for i, item in enumerate(items[:10]):
        buttons.append({"text": str(i + 1), "callback_data": item["callback_data"]})
    rows = [buttons[i : i + 5] for i in range(0, len(buttons), 5)]

    tg_client.send(chat_id, text, reply_markup={"inline_keyboard": rows} if rows else None)


def cmd_meeting(chat_id: int, query: str):
    """
    /פגישה <שעה או טקסט> — חיפוש פגישה.
    If it looks like a time (e.g. "11", "11:00"), search today's meetings.
    Otherwise search by text.
    """
    query = query.strip()
    if not query:
        tg_client.send(chat_id, "שימוש: /פגישה <שעה או טקסט>\nדוגמה: /פגישה 11:00\nאו: /פגישה סינכרון שבועי")
        return

    # Check if it looks like a time
    time_query = query.replace(":", "").replace(".", "")
    if time_query.isdigit() and len(time_query) <= 4:
        _search_meeting_by_time(chat_id, query)
    else:
        _search_meeting_by_text(chat_id, query)


def _search_meeting_by_time(chat_id: int, time_str: str):
    """Search today's meetings for one near the given time."""
    try:
        meetings = notion.query_meetings_by_date(notion.today_str())
    except Exception as e:
        tg_client.send(chat_id, f"שגיאה: {e}")
        return

    if not meetings:
        tg_client.send(chat_id, "אין פגישות היום.")
        return

    # Normalize time query
    t = time_str.replace(":", "").replace(".", "")
    if len(t) <= 2:
        t = t.ljust(4, "0")  # "11" -> "1100"
    target = t[:2] + ":" + t[2:4]

    # Find closest match
    best = None
    for page in meetings:
        date_val = notion.extract_prop(page, "תאריך")
        if "T" in date_val:
            meeting_time = date_val.split("T")[1][:5]
            if meeting_time == target:
                best = page
                break
            if best is None:
                best = page  # fallback to first

    if best:
        card = notion.get_meeting_card(best, full=True)
        text = fmt.format_meeting_full(card)
        tg_client.send(chat_id, text)
    else:
        tg_client.send(chat_id, f"לא מצאתי פגישה בשעה {target} היום.")


def _search_meeting_by_text(chat_id: int, text: str):
    try:
        matches = notion.query_meetings_by_text(text, limit=5)
    except Exception as e:
        tg_client.send(chat_id, f"שגיאה: {e}")
        return

    if not matches:
        tg_client.send(chat_id, f"לא מצאתי פגישה שמכילה '{text}'.")
        return

    if len(matches) == 1:
        card = notion.get_meeting_card(matches[0], full=True)
        tg_client.send(chat_id, fmt.format_meeting_full(card))
        return

    # Multiple — show list with expand
    items = []
    for page in matches:
        card = notion.get_meeting_card(page, full=False)
        expand_id = str(uuid.uuid4())[:8]
        state.EXPAND[expand_id] = {"page_id": page["id"], "db": "meetings"}
        label = card.get("Name", "?")
        date = card.get("תאריך", "")
        items.append({"label": f"{label} ({date})", "callback_data": f"expand_meeting:{expand_id}"})

    tg_client.send_selection(chat_id, f"מצאתי {len(matches)} פגישות:", items)


# ═══════════════════════════════════════════════════
#  UPDATE COMMANDS (עדכון)
# ═══════════════════════════════════════════════════

def cmd_digest(chat_id: int, text: str):
    """
    /סיכום <טקסט חופשי> — LLM מנתח ומציע עדכונים ב-People.
    """
    if not text.strip():
        tg_client.send(
            chat_id,
            "שימוש: /סיכום <טקסט חופשי>\n"
            "דוגמה: /סיכום פגישה עם אלירן: אוהב שחמט, מעדיף הודעות קצרות"
        )
        return

    if not OPENAI_API_KEY:
        tg_client.send(chat_id, "חסר OPENAI_API_KEY ב-Render.")
        return

    try:
        plan = digest_to_plan(text)
    except Exception as e:
        tg_client.send(chat_id, f"שגיאה בקריאה ל-LLM:\n{e}")
        return

    questions = plan.get("questions", [])
    updates = plan.get("updates", [])

    if questions:
        tg_client.send(chat_id, "❓ שאלות הבהרה:\n- " + "\n- ".join(questions))

    high = [u for u in updates if float(u.get("confidence", 0)) >= 0.6]
    if not high:
        tg_client.send(chat_id, "לא מצאתי עדכון בטוח מספיק. נסה לכתוב שם מלא + פרט ברור.")
        return

    # Send proposals one by one (up to 3)
    for u in high[:3]:
        _propose_people_update(chat_id, u["person_name"], u["field"], u["op"], u["value"], u["why"])


def _propose_people_update(chat_id: int, person_name: str, field: str, op: str, value: str, why: str):
    """Find person in Notion and propose update with approval."""
    try:
        matches = notion.query_people(person_name, limit=10)
    except Exception as e:
        tg_client.send(chat_id, f"שגיאה בחיפוש: {e}")
        return

    if not matches:
        tg_client.send(chat_id, f"לא מצאתי אדם בשם '{person_name}'.")
        return

    if len(matches) > 1:
        names = []
        for p in matches[:5]:
            card = notion.get_person_card(p, full=False)
            names.append(f"- {fmt.format_person_list_item(card)}")
        tg_client.send(chat_id, "מצאתי כמה התאמות. כתוב שם מדויק יותר:\n" + "\n".join(names))
        return

    page = matches[0]
    page_id = page["id"]
    page_title = notion.extract_prop(page, "שם") or person_name

    # Get current value for preview
    current = ""
    new_text = value.strip()
    try:
        full = notion.get_page(page_id)
        current = notion.extract_prop(full, field)
        if op == "append" and current.strip():
            new_text = current.strip() + "\n" + value.strip()
    except Exception:
        pass

    approval_id = str(uuid.uuid4())[:8]
    state.PENDING[approval_id] = {
        "chat_id": chat_id,
        "kind": "people_update",
        "payload": {
            "page_id": page_id,
            "page_title": page_title,
            "field": field,
            "op": op,
            "value": value,
            "new_text": new_text,
        },
    }

    text = fmt.format_update_proposal(page_title, field, op, value, why, current)
    tg_client.send_approval(chat_id, text, approval_id)


# ═══════════════════════════════════════════════════
#  SCHEMA / DIAGNOSTICS
# ═══════════════════════════════════════════════════

def cmd_schema(chat_id: int, target: str):
    """/schema <db_name>"""
    if not NOTION_TOKEN:
        tg_client.send(chat_id, "חסר NOTION_TOKEN.")
        return

    schema = notion.get_schema(target)
    if schema is None:
        tg_client.send(chat_id, "שימוש: /schema people|meetings|projects|inbox")
        return

    lines = [f"- {name}: {ptype}" for name, ptype in schema.items()]
    tg_client.send(chat_id, "Schema:\n" + "\n".join(lines[:60]))


def cmd_status(chat_id: int):
    """/סטטוס — diagnostics."""
    checks = {
        "TELEGRAM_TOKEN": bool(NOTION_TOKEN),  # if we got here, it works
        "NOTION_TOKEN": bool(NOTION_TOKEN),
        "OPENAI_API_KEY": bool(OPENAI_API_KEY),
        "PEOPLE_DB": bool(NOTION_PEOPLE_DB_ID),
        "MEETINGS_DB": bool(NOTION_MEETINGS_DB_ID),
        "PROJECTS_DB": bool(NOTION_PROJECTS_DB_ID),
        "INBOX_DB": bool(NOTION_DONNA_INBOX_DB_ID),
    }
    lines = [f"{'✅' if v else '❌'} {k}" for k, v in checks.items()]
    tg_client.send(chat_id, "<b>סטטוס מערכת:</b>\n" + "\n".join(lines))


def cmd_help(chat_id: int):
    """/עזרה — command menu."""
    text = """<b>📋 פקודות דונה:</b>

<b>🔍 חיפוש:</b>
/מי &lt;שם&gt; — כרטיס אדם
/היום — פגישות היום
/מחר — פגישות מחר
/פגישה &lt;שעה או טקסט&gt; — חיפוש פגישה

<b>✏️ עדכון:</b>
/סיכום &lt;טקסט חופשי&gt; — ניתוח טקסט ועדכון People

<b>⚙️ מערכת:</b>
/סטטוס — בדיקת חיבורים
/schema &lt;db&gt; — סכימת דאטהבייס
/עזרה — התפריט הזה"""
    tg_client.send(chat_id, text)


# ═══════════════════════════════════════════════════
#  CALLBACKS (button clicks)
# ═══════════════════════════════════════════════════

def handle_callback(callback_id: str, data: str, chat_id: int):
    """Route callback_query data to the right handler."""

    # Expand person
    if data.startswith("expand_person:"):
        expand_id = data.split(":", 1)[1]
        info = state.EXPAND.pop(expand_id, None)
        if not info:
            tg_client.answer_callback(callback_id, "פג תוקף")
            return
        try:
            page = notion.get_page(info["page_id"])
            card = notion.get_person_card(page, full=True)
            tg_client.answer_callback(callback_id)
            tg_client.send(chat_id, fmt.format_person_full(card))
        except Exception as e:
            tg_client.answer_callback(callback_id, "שגיאה")
            tg_client.send(chat_id, f"שגיאה: {e}")
        return

    # Expand meeting
    if data.startswith("expand_meeting:"):
        expand_id = data.split(":", 1)[1]
        info = state.EXPAND.pop(expand_id, None)
        if not info:
            tg_client.answer_callback(callback_id, "פג תוקף")
            return
        try:
            page = notion.get_page(info["page_id"])
            card = notion.get_meeting_card(page, full=True)
            tg_client.answer_callback(callback_id)
            tg_client.send(chat_id, fmt.format_meeting_full(card))
        except Exception as e:
            tg_client.answer_callback(callback_id, "שגיאה")
            tg_client.send(chat_id, f"שגיאה: {e}")
        return

    # Approve/Reject
    if data.startswith("approve:") or data.startswith("reject:"):
        action, approval_id = data.split(":", 1)
        item = state.PENDING.pop(approval_id, None)
        if not item:
            tg_client.answer_callback(callback_id, "הבקשה כבר טופלה")
            tg_client.send(chat_id, "הבקשה כבר טופלה או לא נמצאה.")
            return

        if action == "reject":
            tg_client.answer_callback(callback_id, "נדחה")
            tg_client.send(chat_id, "נדחה ❌")
            return

        # Approve
        tg_client.answer_callback(callback_id, "אושר")
        kind = item.get("kind")
        payload = item.get("payload", {})

        try:
            if kind == "people_update":
                notion.update_person_field(
                    payload["page_id"], payload["field"], payload["new_text"]
                )
                tg_client.send(
                    chat_id,
                    f"אושר ✅\nעדכנתי: {payload.get('page_title', '')}\nשדה: {payload['field']}"
                )
            else:
                tg_client.send(chat_id, "אושר ✅")
        except Exception as e:
            tg_client.send(chat_id, f"שגיאה בביצוע: {e}")
        return

    # Unknown callback
    tg_client.answer_callback(callback_id, "לא מזוהה")
