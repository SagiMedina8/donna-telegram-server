"""
Donna Agent — Formatters
Format Notion data into nice Telegram messages (Hebrew).
"""

# ──────────────────── People ────────────────────

PERSON_FIELD_LABELS = {
    "שם": "👤 שם",
    "תפקיד": "💼 תפקיד",
    "מחלקה": "🏢 מחלקה",
    "תחום": "📂 תחום",
    "מנהל ישיר": "👆 מנהל ישיר",
    "אופן עבודה מועדף": "💬 אופן עבודה מועדף",
    "תחביבים ותחומי עניין": "🎯 תחביבים ותחומי עניין",
    "טיפים להכנה": "📝 טיפים להכנה",
    "הערות אישיות": "📌 הערות אישיות",
    "הערות רגישות": "⚠️ הערות רגישות",
    "פרוייקטים": "📊 פרויקטים",
    "Meetings": "📅 פגישות",
    "פעיל": "✅ פעיל",
    "לייבלים": "🏷️ לייבלים",
}


def format_person_short(card: dict) -> str:
    """2-3 line summary of a person."""
    name = card.get("שם", "?")
    role = card.get("תפקיד", "")
    dept = card.get("מחלקה", "")
    domain = card.get("תחום", "")

    lines = [f"<b>👤 {name}</b>"]
    if role:
        lines.append(f"💼 {role}")
    details = " · ".join(x for x in [dept, domain] if x)
    if details:
        lines.append(f"🏢 {details}")
    return "\n".join(lines)


def format_person_full(card: dict) -> str:
    """Full person card with all available fields."""
    lines = []
    for field, value in card.items():
        label = PERSON_FIELD_LABELS.get(field, field)
        lines.append(f"{label}: {value}")
    return "\n".join(lines)


def format_person_list_item(card: dict) -> str:
    """One-line summary for selection lists."""
    name = card.get("שם", "?")
    role = card.get("תפקיד", "")
    dept = card.get("מחלקה", "")
    parts = [x for x in [name, role, dept] if x]
    return " | ".join(parts)


# ──────────────────── Meetings ────────────────────

MEETING_FIELD_LABELS = {
    "Name": "📅 כותרת",
    "תאריך": "🕐 תאריך",
    "משתתפים": "👥 משתתפים",
    "מטרה": "🎯 מטרה",
    "תובנות מרכזיות": "💡 תובנות",
    "אפיק": "📊 אפיק",
    "סטטוס": "📋 סטטוס",
}


def format_meeting_short(card: dict) -> str:
    """Short meeting summary (title + time + participants)."""
    name = card.get("Name", "?")
    date = card.get("תאריך", "")
    participants = card.get("משתתפים", "")
    purpose = card.get("מטרה", "")

    lines = [f"<b>📅 {name}</b>"]
    if date:
        # Show only time if same day
        time_part = date.split("T")[1][:5] if "T" in date else date
        lines.append(f"🕐 {time_part}")
    if participants:
        lines.append(f"👥 {participants}")
    if purpose:
        lines.append(f"🎯 {purpose}")
    return "\n".join(lines)


def format_meeting_full(card: dict) -> str:
    """Full meeting card."""
    lines = []
    for field, value in card.items():
        label = MEETING_FIELD_LABELS.get(field, field)
        lines.append(f"{label}: {value}")
    return "\n".join(lines)


def format_meetings_list(meetings: list[dict]) -> str:
    """Format a list of meetings as numbered list (short)."""
    if not meetings:
        return "אין פגישות."
    lines = []
    for i, m in enumerate(meetings, 1):
        name = m.get("Name", "?")
        date = m.get("תאריך", "")
        time_part = ""
        if date and "T" in date:
            time_part = date.split("T")[1][:5]
        prefix = f"  {time_part}" if time_part else ""
        lines.append(f"{i}. <b>{name}</b>{prefix}")
    return "\n".join(lines)


# ──────────────────── Proposals ────────────────────

def format_update_proposal(person_name: str, field: str, op: str, value: str,
                           why: str, current: str = "") -> str:
    """Format a proposed People update for approval."""
    op_label = "הוספה" if op == "append" else "החלפה"
    lines = [
        f"<b>דונה מציעה עדכון:</b>",
        f"👤 אדם: {person_name}",
        f"📝 שדה: {field}",
        f"🔧 פעולה: {op_label}",
        f"💡 סיבה: {why}",
        "",
    ]
    if current:
        lines.append(f"נוכחי: <i>{current}</i>")
    lines.append(f"חדש: <b>{value}</b>")
    return "\n".join(lines)
