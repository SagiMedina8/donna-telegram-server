"""
Donna Agent — Formatters
Format Notion data into Telegram messages (Hebrew).
"""

# ──────────────────── People ────────────────────

PERSON_LABELS = {
    "שם": "👤 שם", "תפקיד": "💼 תפקיד", "מחלקה": "🏢 מחלקה",
    "תחום": "📂 תחום", "מנהל ישיר": "👆 מנהל ישיר",
    "אופן עבודה מועדף": "💬 אופן עבודה", "תחביבים ותחומי עניין": "🎯 תחביבים",
    "טיפים להכנה": "📝 טיפים להכנה", "הערות אישיות": "📌 הערות",
    "הערות רגישות": "⚠️ רגישות", "פרוייקטים": "📊 פרויקטים",
    "Meetings": "📅 פגישות", "פעיל": "✅ פעיל", "לייבלים": "🏷️ לייבלים",
}

def format_person_short(card: dict) -> str:
    name = card.get("שם", "?")
    role = card.get("תפקיד", "")
    dept = card.get("מחלקה", "")
    domain = card.get("תחום", "")
    lines = [f"<b>👤 {name}</b>"]
    if role: lines.append(f"💼 {role}")
    details = " · ".join(x for x in [dept, domain] if x)
    if details: lines.append(f"🏢 {details}")
    return "\n".join(lines)

def format_person_full(card: dict) -> str:
    return "\n".join(f"{PERSON_LABELS.get(f, f)}: {v}" for f, v in card.items())

def format_person_list_item(card: dict) -> str:
    return " | ".join(x for x in [card.get("שם"), card.get("תפקיד"), card.get("מחלקה")] if x)


# ──────────────────── Meetings ────────────────────

MEETING_LABELS = {
    "Name": "📅 כותרת", "תאריך": "🕐 תאריך", "משתתפים": "👥 משתתפים",
    "מטרה": "🎯 מטרה", "תובנות מרכזיות": "💡 תובנות", "אפיק": "📊 אפיק",
    "סטטוס": "📋 סטטוס",
}

def format_meeting_short(card: dict) -> str:
    name = card.get("Name", "?")
    date = card.get("תאריך", "")
    participants = card.get("משתתפים", "")
    purpose = card.get("מטרה", "")
    lines = [f"<b>📅 {name}</b>"]
    if date:
        time_part = date.split("T")[1][:5] if "T" in date else date
        lines.append(f"🕐 {time_part}")
    if participants: lines.append(f"👥 {participants}")
    if purpose: lines.append(f"🎯 {purpose}")
    return "\n".join(lines)

def format_meeting_full(card: dict) -> str:
    return "\n".join(f"{MEETING_LABELS.get(f, f)}: {v}" for f, v in card.items())

def format_meetings_list(cards: list[dict]) -> str:
    if not cards: return "אין פגישות."
    lines = []
    for i, m in enumerate(cards, 1):
        name = m.get("Name", "?")
        date = m.get("תאריך", "")
        time_part = date.split("T")[1][:5] if date and "T" in date else ""
        prefix = f"  {time_part}" if time_part else ""
        lines.append(f"{i}. <b>{name}</b>{prefix}")
    return "\n".join(lines)


# ──────────────────── Tasks ────────────────────

TASK_LABELS = {
    "Task name": "📋 משימה", "Status": "📊 סטטוס", "Due date": "📅 דדליין",
    "עדיפות": "🔥 עדיפות", "פרוייקט": "📂 פרויקט", "Assignee": "👤 אחראי",
}

def format_task_short(card: dict) -> str:
    name = card.get("Task name", "?")
    status = card.get("Status", "")
    due = card.get("Due date", "")
    priority = card.get("עדיפות", "")
    lines = [f"<b>📋 {name}</b>"]
    parts = []
    if status: parts.append(f"📊 {status}")
    if due: parts.append(f"📅 {due}")
    if priority: parts.append(f"🔥 {priority}")
    if parts: lines.append(" · ".join(parts))
    return "\n".join(lines)

def format_task_full(card: dict) -> str:
    return "\n".join(f"{TASK_LABELS.get(f, f)}: {v}" for f, v in card.items())

def format_tasks_list(cards: list[dict]) -> str:
    if not cards: return "אין משימות פתוחות. 🎉"
    lines = []
    for i, t in enumerate(cards, 1):
        name = t.get("Task name", "?")
        status = t.get("Status", "")
        due = t.get("Due date", "")
        parts = [f"<b>{name}</b>"]
        if due: parts.append(f"📅 {due}")
        if status: parts.append(f"[{status}]")
        lines.append(f"{i}. " + " · ".join(parts))
    return "\n".join(lines)


# ──────────────────── Proposals ────────────────────

def format_update_proposal(person_name, field, op, value, why, current="") -> str:
    op_label = "הוספה" if op == "append" else "החלפה"
    lines = [
        f"<b>דונה מציעה עדכון:</b>",
        f"👤 {person_name}", f"📝 שדה: {field}", f"🔧 פעולה: {op_label}",
        f"💡 סיבה: {why}", "",
    ]
    if current: lines.append(f"נוכחי: <i>{current}</i>")
    lines.append(f"חדש: <b>{value}</b>")
    return "\n".join(lines)


# ──────────────────── Creation preview ────────────────────

def format_creation_preview(ctype: str, name: str, fields: dict) -> str:
    """Format a preview of what will be created."""
    type_labels = {"person": "👤 אדם חדש", "meeting": "📅 פגישה חדשה", "task": "📋 משימה חדשה"}
    field_labels = {
        "role": "💼 תפקיד", "department": "🏢 מחלקה", "domain": "📂 תחום",
        "manager": "👆 מנהל ישיר", "work_pref": "💬 אופן עבודה",
        "hobbies": "🎯 תחביבים", "tips": "📝 טיפים", "notes": "📌 הערות",
        "date_iso": "🕐 תאריך", "participants": "👥 משתתפים", "purpose": "🎯 מטרה",
        "due_date": "📅 דדליין", "priority": "🔥 עדיפות", "project": "📂 פרויקט",
    }
    lines = [f"<b>{type_labels.get(ctype, ctype)}: {name}</b>\n"]
    for k, v in fields.items():
        if v and v.strip():
            label = field_labels.get(k, k)
            # Show time nicely for date_iso
            if k == "date_iso" and "T" in v:
                v = v.replace("T", " ").split("+")[0]
            lines.append(f"{label}: {v}")
    return "\n".join(lines)
