"""
Donna Agent — LLM
OpenAI Responses API: intent classifier, digest planner, creation parser.
"""
import json
import requests
from datetime import datetime, timezone
from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE, ALLOWED_PEOPLE_FIELDS


def _headers():
    return {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}


def _call(system: str, user: str, schema: dict, schema_name: str, max_tokens: int = 600) -> dict:
    """Generic OpenAI Responses API call with Structured Outputs."""
    body = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema,
                "strict": True,
            }
        },
        "max_output_tokens": max_tokens,
    }
    r = requests.post(f"{OPENAI_BASE}/responses", headers=_headers(), json=body, timeout=60)
    r.raise_for_status()
    data = r.json()
    out = data.get("output_text")
    if out:
        return json.loads(out)
    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text" and "text" in c:
                return json.loads(c["text"])
    raise RuntimeError("No parsable JSON in OpenAI response")


# ═════════════════════════════════════════════
#  INTENT CLASSIFIER
# ═════════════════════════════════════════════

def classify_intent(user_text: str, context: dict | None = None) -> dict:
    ctx_hint = ""
    if context:
        ctx_hint = f"\nהקשר קודם: נושא='{context.get('topic','')}' ישות='{context.get('entity','')}'"

    system = f"""אתה ממיין הודעות לדונה (מזכירת-על). החזר JSON.
{ctx_hint}
Intents:
- "who": שאלה על אדם (מי זה X, ספר על X)
- "today": פגישות היום (מה יש היום, לוז, יומן)
- "tomorrow": פגישות מחר
- "meeting": חיפוש פגישה ספציפית
- "my_tasks": משימות שלי (מה המשימות, יש לי משימות?)
- "digest": סיכום/עדכון אנשים (נפגשתי עם X הוא אוהב Y)
- "create_person": הוסף אדם חדש (תוסיף את X, אדם חדש)
- "create_meeting": קבע/צור פגישה (קבע פגישה, צור פגישה עם X)
- "create_task": צור משימה (תזכיר לי, יש לי משימה, תוסיף משימה)
- "help": עזרה, מה את יכולה
- "followup_answer": תשובה לשאלת פולואפ
- "chat": שיחה כללית (שלום, תודה, מה שלומך)
- "unknown": לא ברור

entity = השם/נושא שחולץ.
raw = הטקסט המקורי."""

    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "intent": {"type": "string", "enum": [
                "who", "today", "tomorrow", "meeting", "my_tasks",
                "digest", "create_person", "create_meeting", "create_task",
                "help", "followup_answer", "chat", "unknown"
            ]},
            "entity": {"type": "string"},
            "raw": {"type": "string"},
        },
        "required": ["intent", "entity", "raw"],
    }
    return _call(system, user_text, schema, "IntentClassification", 150)


# ═════════════════════════════════════════════
#  DIGEST (People updates)
# ═════════════════════════════════════════════

def digest_to_plan(user_text: str) -> dict:
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M (%A)")
    system = f"""Current time: {now}
אתה Donna, מנתח/ת טקסט חופשי ומחזיר/ה תכנית עדכונים ל-People.

כללי מיפוי:
- "תחביבים ותחומי עניין": ספורט, תחביבים, פנאי
- "אופן עבודה מועדף": איך אוהבים לתקשר (וואטסאפ, קצר, אסינכרוני)
- "טיפים להכנה": איך להתכונן לפגישה (להגיע עם מספרים, דמו)
- "הערות אישיות": fallback — רק מה שלא מתאים לשום שדה
- "תחום": תחום מקצועי
- "תפקיד": כותרת רשמית
- "מחלקה": שם מחלקה
- "מנהל ישיר": שם המנהל
- "הערות רגישות": מידע רגיש

כללים: 1) פצל לשדות שונים 2) הערות אישיות=fallback בלבד 3) confidence 0-1, <0.6=שאל 4) op: append/set"""

    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "questions": {"type": "array", "items": {"type": "string"}},
            "updates": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "person_name": {"type": "string"},
                    "field": {"type": "string", "enum": ALLOWED_PEOPLE_FIELDS},
                    "op": {"type": "string", "enum": ["append", "set"]},
                    "value": {"type": "string"},
                    "confidence": {"type": "number"},
                    "why": {"type": "string"},
                },
                "required": ["person_name", "field", "op", "value", "confidence", "why"],
            }},
        },
        "required": ["questions", "updates"],
    }
    return _call(system, user_text, schema, "DonnaDigestPlan", 800)


# ═════════════════════════════════════════════
#  CREATION PARSER
# ═════════════════════════════════════════════

def parse_creation(user_text: str, creation_type: str) -> dict:
    """Parse free text into structured creation data.
    creation_type: person / meeting / task
    Returns: {name, fields: {}, missing: []}
    """
    now = datetime.now(timezone.utc).astimezone()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
    day_name = now.strftime("%A")

    type_instructions = {
        "person": """סוג: אדם חדש ב-People.
שדות: name (שם, חובה), role (תפקיד), department (מחלקה), domain (תחום), manager (מנהל ישיר), work_pref (אופן עבודה מועדף), hobbies (תחביבים), tips (טיפים להכנה), notes (הערות).
חוק קריטי: מלא רק שדות שהמשתמש ציין במפורש! אל תמציא, אל תנחש, אל תשלים. שדה שלא נאמר = ריק "".
missing = שדות שהמשתמש לא ציין (חוץ מ-name).""",
        "meeting": f"""סוג: פגישה חדשה.
היום: {today} ({day_name}). מחר: {tomorrow}.
שדות: name (כותרת, חובה), date_iso (ISO datetime עם +02:00 timezone, חובה), participants (משתתפים), purpose (מטרה).
אם כתב "מחר ב-11" → date_iso = "{tomorrow}T11:00:00+02:00".
אם כתב "היום ב-14" → date_iso = "{today}T14:00:00+02:00".
חוק קריטי: מלא רק שדות שהמשתמש ציין במפורש! אל תמציא, אל תנחש, אל תשלים.
missing = שדות שהמשתמש לא ציין (חוץ מ-name).""",
        "task": f"""סוג: משימה חדשה.
היום: {today} ({day_name}). מחר: {tomorrow}.
שדות: name (שם המשימה, חובה), due_date (YYYY-MM-DD), priority (גבוהה/בינונית/נמוכה), project (שם פרויקט).
אם כתב "עד יום ראשון" → חשב את התאריך הקרוב.
אם כתב "עד מחר" → due_date = "{tomorrow}".
אם כתב "עד היום ב-11" → due_date = "{today}".
חוק קריטי: מלא רק שדות שהמשתמש ציין במפורש! אל תמציא, אל תנחש, אל תשלים. אם לא נאמר priority = השאר ריק "". אם לא נאמר project = השאר ריק "".
missing = שדות שהמשתמש לא ציין (חוץ מ-name).""",
    }

    system = f"""אתה Donna, מחלץ/ת מידע מטקסט חופשי ליצירת רשומה חדשה.
{type_instructions.get(creation_type, '')}
החזר JSON עם name, fields (dict), missing (list של שמות שדות חסרים)."""

    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "fields": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "role": {"type": "string"},
                    "department": {"type": "string"},
                    "domain": {"type": "string"},
                    "manager": {"type": "string"},
                    "work_pref": {"type": "string"},
                    "hobbies": {"type": "string"},
                    "tips": {"type": "string"},
                    "notes": {"type": "string"},
                    "date_iso": {"type": "string"},
                    "participants": {"type": "string"},
                    "purpose": {"type": "string"},
                    "due_date": {"type": "string"},
                    "priority": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": [
                    "role", "department", "domain", "manager", "work_pref",
                    "hobbies", "tips", "notes", "date_iso", "participants",
                    "purpose", "due_date", "priority", "project",
                ],
            },
            "missing": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "fields", "missing"],
    }
    return _call(system, user_text, schema, "DonnaCreation", 500)
