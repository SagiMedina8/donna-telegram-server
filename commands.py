"""
Donna Agent — Commands v2
Menu, creation flows, cron, natural chat, callbacks.
"""
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import notion_client as notion
import telegram_client as tg
import formatters as fmt
import state
from llm import classify_intent, digest_to_plan, parse_creation
from config import (
    NOTION_TOKEN, OPENAI_API_KEY, OWNER_CHAT_ID, TIMEZONE,
    DB_NAME_MAP, donna_says,
)


# ═══════════════════════════════════════════════════
#  MENU
# ═══════════════════════════════════════════════════

def cmd_start(chat_id: int):
    tg.send_main_menu(chat_id, "💅 <b>היי, אני דונה.</b>\nאני תמיד צעד אחד לפניך.\n\nבחר קטגוריה או פשוט כתוב לי:")


def handle_menu_callback(callback_id: str, data: str, chat_id: int):
    """Handle menu:* and action:* callbacks."""
    tg.answer_callback(callback_id)

    if data == "menu:back":
        cmd_start(chat_id)
        return
    if data == "menu:people":
        tg.send_sub_menu(chat_id, "people")
        return
    if data == "menu:meetings":
        tg.send_sub_menu(chat_id, "meetings")
        return
    if data == "menu:tasks":
        tg.send_sub_menu(chat_id, "tasks")
        return
    if data == "menu:today":
        cmd_today(chat_id)
        return
    if data == "menu:help":
        cmd_help(chat_id)
        return

    # Actions that need text input → set context and prompt
    if data == "action:search_person":
        state.set_context(chat_id, "awaiting_input", "search_person")
        tg.send(chat_id, "🔍 כתוב את שם האדם לחיפוש:")
        return
    if data == "action:add_person":
        state.set_context(chat_id, "awaiting_input", "add_person")
        tg.send(chat_id, "➕ כתוב שם ופרטים, למשל:\n<i>שיר גל, מנהלת מכירות במחלקת Salesforce</i>")
        return
    if data == "action:add_people_batch":
        state.set_context(chat_id, "awaiting_input", "add_people_batch")
        tg.send(chat_id, "👥 כתוב את כל השמות ומאפיינים משותפים, למשל:\n<i>דני כהן, שיר לוי, רון אברהם — צוות פיתוח, מנהל: עידן, תפקיד: מפתח</i>")
        return
    if data == "action:search_meeting":
        state.set_context(chat_id, "awaiting_input", "search_meeting")
        tg.send(chat_id, "🔍 כתוב שם פגישה או שעה (למשל: 14:00):")
        return
    if data == "action:add_meeting":
        state.set_context(chat_id, "awaiting_input", "add_meeting")
        tg.send(chat_id, "➕ כתוב פרטי פגישה, למשל:\n<i>פגישה עם אלירן מחר ב-11, סינכרון שבועי</i>")
        return
    if data == "action:today":
        cmd_today(chat_id)
        return
    if data == "action:tomorrow":
        cmd_tomorrow(chat_id)
        return
    if data == "action:open_tasks":
        cmd_my_tasks(chat_id, "")
        return
    if data == "action:today_tasks":
        cmd_my_tasks(chat_id, "היום")
        return
    if data == "action:add_task":
        state.set_context(chat_id, "awaiting_input", "add_task")
        tg.send(chat_id, "➕ כתוב משימה, למשל:\n<i>לשלוח מייל לנורית עד יום ראשון</i>")
        return


# ═══════════════════════════════════════════════════
#  READ COMMANDS
# ═══════════════════════════════════════════════════

def cmd_who(chat_id: int, name: str):
    if not name.strip():
        tg.send(chat_id, "שימוש: /מי <שם>\nדוגמה: /מי אלירן")
        return
    try:
        matches = notion.query_people(name.strip(), limit=10)
    except Exception as e:
        tg.send(chat_id, f"{donna_says('error')}\n{e}")
        return
    if not matches:
        tg.send(chat_id, donna_says("no_results"))
        return
    if len(matches) == 1:
        _show_person(chat_id, matches[0])
        return
    items = []
    for page in matches[:10]:
        card = notion.get_person_card(page, full=False)
        eid = str(uuid.uuid4())[:8]
        state.EXPAND[eid] = {"page_id": page["id"], "db": "people"}
        items.append({"label": fmt.format_person_list_item(card), "callback_data": f"exp_p:{eid}"})
    tg.send_selection(chat_id, f"מצאתי {len(matches)} תוצאות:", items)


def _show_person(chat_id: int, page: dict):
    card = notion.get_person_card(page, full=False)
    text = fmt.format_person_short(card)
    eid = str(uuid.uuid4())[:8]
    state.EXPAND[eid] = {"page_id": page["id"], "db": "people"}
    tg.send_with_expand(chat_id, text, f"exp_p:{eid}")
    state.set_context(chat_id, "person", card.get("שם", ""))


def cmd_today(chat_id: int):
    _show_meetings(chat_id, notion.today_str(), "היום")

def cmd_tomorrow(chat_id: int):
    _show_meetings(chat_id, notion.tomorrow_str(), "מחר")

def _show_meetings(chat_id: int, date_str: str, label: str):
    try:
        meetings = notion.query_meetings_by_date(date_str)
    except Exception as e:
        tg.send(chat_id, f"{donna_says('error')}\n{e}")
        return
    if not meetings:
        tg.send(chat_id, f"אין פגישות ל{label} ({date_str}). 📭")
        return
    cards = []
    buttons = []
    for page in meetings:
        card = notion.get_meeting_card(page, full=False)
        cards.append(card)
        eid = str(uuid.uuid4())[:8]
        state.EXPAND[eid] = {"page_id": page["id"], "db": "meetings"}
        buttons.append({"text": str(len(buttons) + 1), "callback_data": f"exp_m:{eid}"})
    header = f"<b>📅 פגישות {label} ({date_str}):</b>"
    text = f"{header}\n\n{fmt.format_meetings_list(cards)}"
    rows = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]
    tg.send(chat_id, text, reply_markup={"inline_keyboard": rows} if rows else None)


def cmd_meeting(chat_id: int, query: str):
    query = query.strip()
    if not query:
        tg.send(chat_id, "שימוש: /פגישה <שעה או טקסט>")
        return
    time_q = query.replace(":", "").replace(".", "")
    if time_q.isdigit() and len(time_q) <= 4:
        _search_meeting_time(chat_id, query)
    else:
        _search_meeting_text(chat_id, query)

def _search_meeting_time(chat_id: int, time_str: str):
    try:
        meetings = notion.query_meetings_by_date(notion.today_str())
    except Exception as e:
        tg.send(chat_id, f"{donna_says('error')}\n{e}")
        return
    if not meetings:
        tg.send(chat_id, "אין פגישות היום.")
        return
    t = time_str.replace(":", "").replace(".", "")
    if len(t) <= 2: t = t.ljust(4, "0")
    target = t[:2] + ":" + t[2:4]
    for page in meetings:
        dv = notion.extract_prop(page, "תאריך")
        if "T" in dv and dv.split("T")[1][:5] == target:
            card = notion.get_meeting_card(page, full=True)
            tg.send(chat_id, fmt.format_meeting_full(card))
            return
    tg.send(chat_id, f"לא מצאתי פגישה ב-{target} היום.")

def _search_meeting_text(chat_id: int, text: str):
    try:
        matches = notion.query_meetings_by_text(text, limit=5)
    except Exception as e:
        tg.send(chat_id, f"{donna_says('error')}\n{e}")
        return
    if not matches:
        tg.send(chat_id, donna_says("no_results"))
        return
    if len(matches) == 1:
        card = notion.get_meeting_card(matches[0], full=True)
        tg.send(chat_id, fmt.format_meeting_full(card))
        return
    items = []
    for page in matches:
        card = notion.get_meeting_card(page, full=False)
        eid = str(uuid.uuid4())[:8]
        state.EXPAND[eid] = {"page_id": page["id"], "db": "meetings"}
        items.append({"label": card.get("Name", "?"), "callback_data": f"exp_m:{eid}"})
    tg.send_selection(chat_id, f"מצאתי {len(matches)} פגישות:", items)


def cmd_my_tasks(chat_id: int, query: str = ""):
    try:
        if query.strip() in ("היום", "today"):
            tasks = notion.query_tasks_by_date(notion.today_str())
        else:
            tasks = notion.query_tasks_open(limit=15)
    except Exception as e:
        tg.send(chat_id, f"{donna_says('error')}\n{e}")
        return
    cards = [notion.get_task_card(t) for t in tasks]
    text = fmt.format_tasks_list(cards)
    header = "<b>📋 משימות פתוחות:</b>" if not query.strip() else f"<b>📋 משימות ל{query}:</b>"
    tg.send(chat_id, f"{header}\n\n{text}")


# ═══════════════════════════════════════════════════
#  UPDATE (DIGEST)
# ═══════════════════════════════════════════════════

def cmd_digest(chat_id: int, text: str):
    if not text.strip():
        tg.send(chat_id, "שימוש: /סיכום <טקסט חופשי>\nדוגמה: /סיכום נפגשתי עם אלירן, הוא אוהב שחמט")
        return
    try:
        plan = digest_to_plan(text)
    except Exception as e:
        tg.send(chat_id, f"{donna_says('error')}\n{e}")
        return
    questions = plan.get("questions", [])
    updates = plan.get("updates", [])
    if questions:
        tg.send(chat_id, "❓ שאלות הבהרה:\n- " + "\n- ".join(questions))
    high = [u for u in updates if float(u.get("confidence", 0)) >= 0.6]
    if not high:
        tg.send(chat_id, "לא מצאתי עדכון בטוח מספיק. נסה עם שם מלא + פרט ברור.")
        return
    for u in high[:3]:
        _propose_update(chat_id, u["person_name"], u["field"], u["op"], u["value"], u["why"])


def _propose_update(chat_id, person_name, field, op, value, why):
    try:
        matches = notion.query_people(person_name, limit=5)
    except Exception as e:
        tg.send(chat_id, f"{donna_says('error')}\n{e}")
        return
    if not matches:
        tg.send(chat_id, f"לא מצאתי אדם בשם '{person_name}'.")
        return
    if len(matches) > 1:
        names = [f"- {fmt.format_person_list_item(notion.get_person_card(p, False))}" for p in matches[:5]]
        tg.send(chat_id, "מצאתי כמה. כתוב שם מדויק יותר:\n" + "\n".join(names))
        return
    page = matches[0]
    page_id = page["id"]
    page_title = notion.extract_prop(page, "שם") or person_name
    current = ""
    new_text = value.strip()
    try:
        full = notion.get_page(page_id)
        current = notion.extract_prop(full, field)
        if op == "append" and current.strip():
            new_text = current.strip() + "\n" + value.strip()
    except Exception:
        pass
    aid = str(uuid.uuid4())[:8]
    state.PENDING[aid] = {
        "chat_id": chat_id, "kind": "people_update",
        "payload": {"page_id": page_id, "page_title": page_title, "field": field, "op": op, "value": value, "new_text": new_text},
    }
    text = fmt.format_update_proposal(page_title, field, op, value, why, current)
    tg.send_approval(chat_id, text, aid)


# ═══════════════════════════════════════════════════
#  CREATION
# ═══════════════════════════════════════════════════

# Fields relevant to each type
TYPE_FIELDS = {
    "person": ["role", "department", "domain", "manager", "work_pref", "hobbies", "tips", "notes"],
    "meeting": ["date_iso", "participants", "purpose"],
    "task": ["due_date", "priority", "project"],
}


def handle_create(chat_id: int, ctype: str, raw_text: str):
    if not raw_text.strip():
        examples = {
            "person": "דוגמה: תוסיף את שיר גל, מנהלת מכירות במחלקת Salesforce",
            "meeting": "דוגמה: קבע פגישה עם אלירן מחר ב-11, סינכרון שבועי",
            "task": "דוגמה: תזכיר לי לשלוח מייל לנורית עד יום ראשון",
        }
        tg.send(chat_id, examples.get(ctype, "מה ליצור?"))
        return

    try:
        parsed = parse_creation(raw_text, ctype)
    except Exception as e:
        tg.send(chat_id, f"{donna_says('error')}\n{e}")
        return

    name = parsed.get("name", "").strip()
    # Filter only relevant fields for this type
    allowed = TYPE_FIELDS.get(ctype, [])
    fields = {k: v for k, v in parsed.get("fields", {}).items() if v and v.strip() and k in allowed}
    # Filter missing to only relevant fields
    missing = [m for m in parsed.get("missing", []) if m in allowed]

    if not name:
        tg.send(chat_id, "לא הצלחתי לזהות שם. נסה שוב עם יותר פרטים.")
        return

    aid = str(uuid.uuid4())[:8]
    state.PENDING[aid] = {
        "chat_id": chat_id, "kind": f"create_{ctype}",
        "payload": {"name": name, "fields": fields, "missing": missing},
    }

    preview = fmt.format_creation_preview(ctype, name, fields)
    has_missing = len(missing) > 0

    if has_missing:
        state.start_creation(chat_id, ctype, {"name": name, **fields}, missing)
        tg.send(chat_id, preview, reply_markup={
            "inline_keyboard": [
                [{"text": "❓ שאלי אותי עוד", "callback_data": f"ask_more:{aid}"}],
                [{"text": "✅ צרי עם מה שיש", "callback_data": f"approve:{aid}"}],
                [{"text": "❌ ביטול", "callback_data": f"reject:{aid}"}],
            ]
        })
    else:
        tg.send_approval(chat_id, preview, aid)


def _ask_all_missing(chat_id: int):
    """Send ALL missing fields in one message, type-filtered."""
    flow = state.get_creation(chat_id)
    if not flow:
        return

    ctype = flow["type"]
    # Filter missing to only this type's fields
    allowed = TYPE_FIELDS.get(ctype, [])
    missing = [m for m in flow["missing"] if m in allowed]
    flow["missing"] = missing  # update

    if not missing:
        _finalize_creation(chat_id)
        return

    text = fmt.format_missing_questions(ctype, missing)
    if not text:
        _finalize_creation(chat_id)
        return

    state.set_context(chat_id, "creation_fill", ctype, {"missing_fields": missing})
    tg.send(chat_id, text)


def _handle_creation_fill(chat_id: int, text: str):
    """Parse numbered answers: '1. PM\n2. מוצרים' or 'סיים'."""
    flow = state.get_creation(chat_id)
    if not flow:
        return

    if text.strip() in ("סיים", "סיימי", "יאללה", "done"):
        _finalize_creation(chat_id)
        return

    ctype = flow["type"]
    allowed = TYPE_FIELDS.get(ctype, [])
    missing = [m for m in flow["missing"] if m in allowed]

    # Parse numbered answers
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Try "1. value" or "1: value" or "1 value"
        parts = None
        for sep in [". ", ": ", " - ", "- ", " "]:
            if sep in line:
                idx_str, val = line.split(sep, 1)
                idx_str = idx_str.strip().rstrip(".")
                if idx_str.isdigit():
                    parts = (int(idx_str), val.strip())
                    break

        if parts and 1 <= parts[0] <= len(missing):
            field = missing[parts[0] - 1]
            state.advance_creation(chat_id, field, parts[1])

    _finalize_creation(chat_id)


def _finalize_creation(chat_id: int):
    """Show final preview and ask for confirmation."""
    flow = state.get_creation(chat_id)
    if not flow:
        return

    ctype = flow["type"]
    name = flow["data"].get("name", "")
    allowed = TYPE_FIELDS.get(ctype, [])
    fields = {k: v for k, v in flow["data"].items() if k in allowed and v and v.strip()}

    aid = str(uuid.uuid4())[:8]
    state.PENDING[aid] = {
        "chat_id": chat_id, "kind": f"create_{ctype}",
        "payload": {"name": name, "fields": fields},
    }

    preview = fmt.format_creation_preview(ctype, name, fields)
    state.end_creation(chat_id)
    state.clear_context(chat_id)
    tg.send_approval(chat_id, f"{preview}\n\nליצור?", aid)


def _execute_creation(chat_id: int, ctype: str, payload: dict):
    name = payload["name"]
    fields = payload.get("fields", {})
    try:
        if ctype == "person":
            field_map = {
                "role": "תפקיד", "department": "מחלקה", "domain": "תחום",
                "manager": "מנהל ישיר", "work_pref": "אופן עבודה מועדף",
                "hobbies": "תחביבים ותחומי עניין", "tips": "טיפים להכנה", "notes": "הערות אישיות",
            }
            notion_fields = {heb: fields[eng] for eng, heb in field_map.items() if fields.get(eng)}
            notion.create_person(name, notion_fields)

        elif ctype == "meeting":
            date_iso = fields.get("date_iso", "")
            mf = {}
            if fields.get("participants"): mf["משתתפים"] = fields["participants"]
            if fields.get("purpose"): mf["מטרה"] = fields["purpose"]
            notion.create_meeting(name, date_iso, mf)

        elif ctype == "task":
            project_id = ""
            if fields.get("project"):
                project_id = notion.find_project_id(fields["project"]) or ""
            notion.create_task(name, fields.get("due_date", ""), fields.get("priority", ""), project_id)

        tg.send(chat_id, f"{donna_says('creation')}\n<b>{name}</b> נוצר בהצלחה.")

    except Exception as e:
        tg.send(chat_id, f"{donna_says('error')}\n{e}")


# ═══════════════════════════════════════════════════
#  BATCH CREATION (Multiple people)
# ═══════════════════════════════════════════════════

def handle_batch_people(chat_id: int, text: str):
    """Parse 'דני כהן, שיר לוי, רון אברהם — צוות פיתוח, מנהל: עידן, תפקיד: מפתח'"""
    if "—" in text:
        names_part, attrs_part = text.split("—", 1)
    elif "-" in text and "," in text.split("-", 1)[0]:
        names_part, attrs_part = text.split("-", 1)
    else:
        names_part = text
        attrs_part = ""

    names = [n.strip() for n in names_part.split(",") if n.strip()]
    if not names:
        tg.send(chat_id, "לא זיהיתי שמות. כתוב שמות מופרדים בפסיק.")
        return

    # Parse shared attributes
    shared = {}
    attr_map = {
        "תפקיד": "תפקיד", "role": "תפקיד",
        "מחלקה": "מחלקה", "dept": "מחלקה", "department": "מחלקה",
        "צוות": "מחלקה", "team": "מחלקה",
        "מנהל": "מנהל ישיר", "manager": "מנהל ישיר",
        "תחום": "תחום", "domain": "תחום",
    }
    if attrs_part:
        for attr in attrs_part.split(","):
            attr = attr.strip()
            if ":" in attr:
                key, val = attr.split(":", 1)
                key = key.strip().lower()
                val = val.strip()
                notion_field = attr_map.get(key, "")
                if notion_field:
                    shared[notion_field] = val
            else:
                # No colon — guess it's a team/department
                shared["מחלקה"] = attr.strip()

    # Preview
    lines = [f"<b>👥 הוספת {len(names)} אנשים:</b>\n"]
    for n in names:
        lines.append(f"• {n}")
    if shared:
        lines.append("\n<b>מאפיינים משותפים:</b>")
        for k, v in shared.items():
            lines.append(f"  {k}: {v}")

    aid = str(uuid.uuid4())[:8]
    state.PENDING[aid] = {
        "chat_id": chat_id, "kind": "batch_people",
        "payload": {"names": names, "shared": shared},
    }
    tg.send_approval(chat_id, "\n".join(lines), aid)


def _execute_batch_people(chat_id: int, payload: dict):
    names = payload["names"]
    shared = payload.get("shared", {})
    created = []
    errors = []
    for name in names:
        try:
            notion.create_person(name, shared)
            created.append(name)
        except Exception as e:
            errors.append(f"{name}: {e}")

    msg = f"{donna_says('creation')}\n\n✅ נוצרו {len(created)} אנשים:"
    for n in created:
        msg += f"\n• {n}"
    if errors:
        msg += f"\n\n❌ שגיאות:"
        for e in errors:
            msg += f"\n• {e}"
    tg.send(chat_id, msg)


# ═══════════════════════════════════════════════════
#  CRON: MORNING BRIEF
# ═══════════════════════════════════════════════════

def send_morning_brief(chat_id: int):
    today = notion.today_str()
    try:
        meetings = notion.query_meetings_by_date(today)
    except Exception as e:
        tg.send(chat_id, f"{donna_says('error')}\n{e}")
        return
    try:
        tasks = notion.query_tasks_by_date(today)
    except Exception:
        tasks = []

    if not meetings and not tasks:
        tg.send(chat_id, f"{donna_says('morning')}\nאין פגישות ולא משימות מתוכננות להיום. יום רגוע! 😌")
        return

    lines = [donna_says("morning"), ""]

    if meetings:
        lines.append(f"<b>📅 {len(meetings)} פגישות:</b>")
        for i, page in enumerate(meetings, 1):
            card = notion.get_meeting_card(page, full=False)
            name = card.get("Name", "?")
            date = card.get("תאריך", "")
            time_part = date.split("T")[1][:5] if "T" in date else ""
            participants = card.get("משתתפים", "")
            purpose = card.get("מטרה", "")
            lines.append(f"\n<b>{i}. {name}</b>{'  🕐 ' + time_part if time_part else ''}")
            if participants: lines.append(f"   👥 {participants}")
            if purpose: lines.append(f"   🎯 {purpose}")
            if participants:
                for pname in [n.strip() for n in participants.replace("،", ",").split(",")][:4]:
                    if not pname: continue
                    try:
                        people = notion.query_people(pname, limit=1)
                        if people:
                            tips = notion.extract_prop(people[0], "טיפים להכנה")
                            role = notion.extract_prop(people[0], "תפקיד")
                            if tips or role:
                                recap = f"   💡 {pname}"
                                if role: recap += f" ({role})"
                                if tips: recap += f" — {tips[:80]}"
                                lines.append(recap)
                    except Exception:
                        pass

    if tasks:
        task_cards = [notion.get_task_card(t) for t in tasks]
        lines.append(f"\n<b>📋 {len(tasks)} משימות להיום:</b>")
        lines.append(fmt.format_tasks_list(task_cards))

    lines.append("\n💪 יום פרודוקטיבי!")
    tg.send(chat_id, "\n".join(lines))


# ═══════════════════════════════════════════════════
#  CRON: FOLLOWUP
# ═══════════════════════════════════════════════════

def check_ended_meetings(chat_id: int):
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")
    try:
        meetings = notion.query_meetings_by_date(today)
    except Exception:
        return
    for page in meetings:
        page_id = page["id"]
        if state.was_followed_up(page_id):
            continue
        date_val = notion.extract_prop(page, "תאריך")
        if "T" not in date_val:
            continue
        try:
            start = datetime.fromisoformat(date_val)
            end = start + timedelta(minutes=30)
        except Exception:
            continue
        if end <= now <= end + timedelta(minutes=15):
            state.mark_followed_up(page_id, today)
            name = notion.extract_prop(page, "Name")
            participants = notion.extract_prop(page, "משתתפים")
            msg = donna_says("followup")
            msg += f"\n\n<b>{name}</b> הסתיימה."
            if participants: msg += f"\n👥 עם: {participants}"
            msg += "\n\nמה היה? תובנות? משימות? פשוט כתוב ואני אעדכן."
            tg.send(chat_id, msg)
            state.set_context(chat_id, "followup", name)
            return


# ═══════════════════════════════════════════════════
#  NATURAL CHAT (Intent Router)
# ═══════════════════════════════════════════════════

def handle_natural_text(chat_id: int, text: str):
    ctx = state.get_context(chat_id)

    # Check if in creation fill mode (answering numbered questions)
    if ctx and ctx.get("topic") == "creation_fill":
        _handle_creation_fill(chat_id, text)
        return

    # Check if awaiting input from menu button
    if ctx and ctx.get("topic") == "awaiting_input":
        action = ctx.get("entity", "")
        state.clear_context(chat_id)
        if action == "search_person":
            cmd_who(chat_id, text)
        elif action == "add_person":
            handle_create(chat_id, "person", text)
        elif action == "add_people_batch":
            handle_batch_people(chat_id, text)
        elif action == "search_meeting":
            cmd_meeting(chat_id, text)
        elif action == "add_meeting":
            handle_create(chat_id, "meeting", text)
        elif action == "add_task":
            handle_create(chat_id, "task", text)
        return

    # Classify intent via LLM
    try:
        result = classify_intent(text, ctx)
    except Exception as e:
        tg.send(chat_id, f"לא הצלחתי להבין. נסה שוב או /עזרה\n({e})")
        return

    intent = result.get("intent", "unknown")
    entity = result.get("entity", "")

    if intent == "who":
        state.set_context(chat_id, "person", entity)
        cmd_who(chat_id, entity)
    elif intent == "today":
        cmd_today(chat_id)
    elif intent == "tomorrow":
        cmd_tomorrow(chat_id)
    elif intent == "meeting":
        state.set_context(chat_id, "meeting", entity)
        cmd_meeting(chat_id, entity)
    elif intent == "my_tasks":
        cmd_my_tasks(chat_id, entity)
    elif intent == "digest" or intent == "followup_answer":
        if ctx and ctx.get("topic") == "followup":
            text = f"סיכום פגישה '{ctx.get('entity', '')}': {text}"
        state.set_context(chat_id, "digest", entity)
        cmd_digest(chat_id, text)
    elif intent == "create_person":
        handle_create(chat_id, "person", entity or text)
    elif intent == "create_meeting":
        handle_create(chat_id, "meeting", entity or text)
    elif intent == "create_task":
        handle_create(chat_id, "task", entity or text)
    elif intent == "help":
        cmd_help(chat_id)
    elif intent == "chat":
        _handle_chat(chat_id, text)
    else:
        if ctx and ctx.get("topic") == "person":
            cmd_who(chat_id, ctx.get("entity", ""))
        else:
            tg.send(chat_id, "לא הבנתי 🤔\nנסה: מי זה X? מה יש היום? תוסיף משימה... או /עזרה")


def _handle_chat(chat_id: int, text: str):
    lower = text.lower().strip()
    for kw in ["תודה", "תנקס", "thanks"]:
        if kw in lower:
            tg.send(chat_id, donna_says("thanks"))
            return
    for kw in ["שלום", "היי", "הי", "בוקר", "ערב"]:
        if kw in lower:
            tg.send(chat_id, donna_says("greeting"))
            return
    if any(kw in lower for kw in ["מה שלומך", "מה נשמע", "מה קורה"]):
        tg.send(chat_id, "הכל תחת שליטה 😎 מה אפשר לסדר?")
        return
    if any(kw in lower for kw in ["מי את", "מה את"]):
        tg.send(chat_id, "אני דונה. 💅 אני יודעת הכל, ואני תמיד צעד אחד לפניך.\nכתוב /עזרה לרשימת פקודות.")
        return
    tg.send(chat_id, donna_says("greeting"))


# ═══════════════════════════════════════════════════
#  SYSTEM
# ═══════════════════════════════════════════════════

def cmd_schema(chat_id: int, target: str):
    if not NOTION_TOKEN:
        tg.send(chat_id, "חסר NOTION_TOKEN.")
        return
    db_id = DB_NAME_MAP.get(target.strip().lower(), "")
    if not db_id:
        tg.send(chat_id, "שימוש:\n/schema people|meetings|projects|inbox|משימות")
        return
    try:
        schema = notion.get_schema(target)
        if not schema:
            tg.send(chat_id, "לא הצלחתי לשלוף סכימה.")
            return
        lines = [f"- {n}: {t}" for n, t in schema.items()]
        tg.send(chat_id, "Schema:\n" + "\n".join(lines[:60]))
    except Exception as e:
        tg.send(chat_id, f"{donna_says('error')}\n{e}")


def cmd_status(chat_id: int):
    from config import NOTION_PEOPLE_DB_ID, NOTION_MEETINGS_DB_ID, NOTION_PROJECTS_DB_ID, NOTION_TASKS_DB_ID
    checks = {
        "TELEGRAM": True, "NOTION": bool(NOTION_TOKEN), "OPENAI": bool(OPENAI_API_KEY),
        "PEOPLE_DB": bool(NOTION_PEOPLE_DB_ID), "MEETINGS_DB": bool(NOTION_MEETINGS_DB_ID),
        "PROJECTS_DB": bool(NOTION_PROJECTS_DB_ID), "TASKS_DB": bool(NOTION_TASKS_DB_ID),
        "OWNER_CHAT_ID": bool(OWNER_CHAT_ID),
    }
    lines = [f"{'✅' if v else '❌'} {k}" for k, v in checks.items()]
    tg.send(chat_id, f"<b>סטטוס דונה:</b>\n" + "\n".join(lines))


def cmd_chatid(chat_id: int):
    tg.send(chat_id, f"ה-Chat ID שלך: <code>{chat_id}</code>")


def cmd_help(chat_id: int):
    text = """<b>💅 דונה — מה אני יודעת לעשות:</b>

<b>🔍 חיפוש:</b>
/מי &lt;שם&gt; — כרטיס אדם
/היום — פגישות היום
/מחר — פגישות מחר
/פגישה &lt;שעה/טקסט&gt; — חיפוש
/משימות — משימות פתוחות

<b>✏️ עדכון:</b>
/סיכום &lt;טקסט&gt; — ניתוח ועדכון People

<b>🆕 יצירה:</b>
/אדם_חדש · /פגישה_חדשה · /משימה_חדשה

<b>💬 או פשוט תדבר איתי:</b>
"מי זה אלירן?" · "מה יש מחר?"
"תוסיף משימה..." · "תזכיר לי..."

<b>📌 תפריט:</b> /start"""
    tg.send(chat_id, text)


# ═══════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════

def handle_callback(callback_id: str, data: str, chat_id: int):

    # Menu / Action
    if data.startswith("menu:") or data.startswith("action:"):
        handle_menu_callback(callback_id, data, chat_id)
        return

    # Expand person
    if data.startswith("exp_p:"):
        eid = data.split(":", 1)[1]
        info = state.EXPAND.pop(eid, None)
        if not info:
            tg.answer_callback(callback_id, "פג תוקף")
            return
        try:
            page = notion.get_page(info["page_id"])
            card = notion.get_person_card(page, full=True)
            tg.answer_callback(callback_id)
            tg.send(chat_id, fmt.format_person_full(card))
        except Exception as e:
            tg.answer_callback(callback_id, "שגיאה")
            tg.send(chat_id, f"שגיאה: {e}")
        return

    # Expand meeting
    if data.startswith("exp_m:"):
        eid = data.split(":", 1)[1]
        info = state.EXPAND.pop(eid, None)
        if not info:
            tg.answer_callback(callback_id, "פג תוקף")
            return
        try:
            page = notion.get_page(info["page_id"])
            card = notion.get_meeting_card(page, full=True)
            tg.answer_callback(callback_id)
            tg.send(chat_id, fmt.format_meeting_full(card))
        except Exception as e:
            tg.answer_callback(callback_id, "שגיאה")
            tg.send(chat_id, f"שגיאה: {e}")
        return

    # Ask more questions (creation flow) — all at once
    if data.startswith("ask_more:"):
        aid = data.split(":", 1)[1]
        state.PENDING.pop(aid, None)
        tg.answer_callback(callback_id, "שואלת...")
        _ask_all_missing(chat_id)
        return

    # Approve / Reject
    if data.startswith("approve:") or data.startswith("reject:"):
        action, aid = data.split(":", 1)
        item = state.PENDING.pop(aid, None)
        if not item:
            tg.answer_callback(callback_id, "כבר טופל")
            tg.send(chat_id, "הבקשה כבר טופלה.")
            return

        if action == "reject":
            tg.answer_callback(callback_id, "נדחה")
            tg.send(chat_id, donna_says("rejection"))
            state.end_creation(chat_id)
            return

        tg.answer_callback(callback_id, "מאושר")
        kind = item.get("kind", "")
        payload = item.get("payload", {})

        try:
            if kind == "people_update":
                notion.update_person_field(payload["page_id"], payload["field"], payload["new_text"])
                tg.send(chat_id, f"{donna_says('approval')}\nעדכנתי: {payload.get('page_title','')}\nשדה: {payload['field']}")
            elif kind == "batch_people":
                _execute_batch_people(chat_id, payload)
            elif kind.startswith("create_"):
                ctype = kind.replace("create_", "")
                _execute_creation(chat_id, ctype, payload)
                state.end_creation(chat_id)
            else:
                tg.send(chat_id, donna_says("approval"))
        except Exception as e:
            tg.send(chat_id, f"{donna_says('error')}\n{e}")
        return

    tg.answer_callback(callback_id, "לא מזוהה")
