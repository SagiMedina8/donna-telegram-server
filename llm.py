"""
Donna Agent — LLM
OpenAI Responses API integration with Structured Outputs.
"""
import json
import requests
from datetime import datetime, timezone
from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE, ALLOWED_PEOPLE_FIELDS


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }


def digest_to_plan(user_text: str) -> dict:
    """
    Analyze free text and return a structured update plan.
    Returns: {"questions": [...], "updates": [...]}
    Each update: {person_name, field, op, value, confidence, why}
    """
    schema = {
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
                        "confidence": {"type": "number"},
                        "why": {"type": "string"},
                    },
                    "required": ["person_name", "field", "op", "value", "confidence", "why"],
                },
            },
        },
        "required": ["questions", "updates"],
    }

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M (%A)")

    system = f"""Current time: {now}
אתה Donna, עוזר/ת תפעולי/ת שמנתח/ת טקסט חופשי ומחזיר/ה תכנית עדכונים לדאטהבייס People.

כללי מיפוי לשדות:
- "תחביבים ותחומי עניין": ספורט, תחביבים, תחומי ידע, העדפות פנאי (שחמט, ריצה, קריאה)
- "אופן עבודה מועדף": איך הם אוהבים לתקשר ולעבוד (וואטסאפ, קצר וענייני, אסינכרוני, לא פגישות בבוקר)
- "טיפים להכנה": איך להתכונן לפגישה איתם (להגיע עם מספרים, להראות דמו, לא לאחר)
- "הערות אישיות": דברים כלליים שלא מתאימים לקטגוריות למעלה
- "תחום": תחום מקצועי (ביטוח, פיתוח, דאטה, פיננסי)
- "תפקיד": כותרת תפקיד רשמית (מנהל מוצר, מפתח בכיר)
- "מחלקה": שם מחלקה (דאטה ו-AI, פיתוח, מוצר)
- "מנהל ישיר": שם המנהל הישיר
- "הערות רגישות": מידע רגיש (מצב בריאותי, סכסוכים, בעיות אישיות)

כללים:
1) פצל עובדות שונות לשדות שונים. לא לשים הכל ב"הערות אישיות".
2) "הערות אישיות" = fallback רק למה שלא מתאים לשום שדה אחר.
3) confidence: 0-1. מתחת ל-0.6 = שאל שאלה במקום להציע עדכון.
4) person_name = השם כפי שמופיע בטקסט.
5) op: "append" להוסיף למידע קיים, "set" להחליף לגמרי (רק אם בטוח).
6) אם אין מספיק מידע — הוסף שאלה ב-questions.
"""

    body = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "DonnaDigestPlan",
                "schema": schema,
                "strict": True,
            }
        },
        "max_output_tokens": 800,
    }

    r = requests.post(f"{OPENAI_BASE}/responses", headers=_headers(), json=body, timeout=60)
    r.raise_for_status()
    data = r.json()

    # Try convenience field first
    out = data.get("output_text")
    if out:
        return json.loads(out)

    # Fallback: walk output array
    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text" and "text" in c:
                return json.loads(c["text"])

    raise RuntimeError("OpenAI response had no parsable JSON")

def classify_intent(user_text: str, context: dict | None = None) -> dict:
    """
    Classify free text into an intent + extracted entity.
    Returns: {"intent": str, "entity": str, "raw": str}
    Intents: who, today, tomorrow, meeting, digest, help, chat, unknown
    """
    ctx_hint = ""
    if context:
        ctx_hint = f"\nהקשר קודם: הנושא היה '{context.get('topic', '')}' על '{context.get('entity', '')}'"

    system = f"""אתה ממיין הודעות. החזר JSON בלבד.
הודעה מהמשתמש -> intent + entity.

Intents אפשריים:
- "who": שאלה על אדם (מי זה X, ספר לי על X, מה אני יודע על X)
- "today": פגישות היום (מה יש לי היום, איזה פגישות, לוז היום)
- "tomorrow": פגישות מחר
- "meeting": חיפוש פגישה ספציפית (מה הפגישה ב-11, הפגישה עם X)
- "digest": סיכום/עדכון People (נפגשתי עם X, הוא אוהב Y, עדכן את Z)
- "help": עזרה, מה אתה יכול לעשות
- "followup_answer": תשובה לשאלת פולואפ (סיכום פגישה, מה היה)
- "chat": שיחה כללית, שלום, מה שלומך
- "unknown": לא ברור
{ctx_hint}
החזר רק: {{"intent": "...", "entity": "...", "raw": "..."}}
entity = השם/נושא שחולץ (או "" אם אין).
raw = הטקסט המקורי."""

    body = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "IntentClassification",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "intent": {"type": "string", "enum": [
                            "who", "today", "tomorrow", "meeting",
                            "digest", "help", "followup_answer", "chat", "unknown"
                        ]},
                        "entity": {"type": "string"},
                        "raw": {"type": "string"},
                    },
                    "required": ["intent", "entity", "raw"],
                },
                "strict": True,
            }
        },
        "max_output_tokens": 150,
    }

    r = requests.post(f"{OPENAI_BASE}/responses", headers=_headers(), json=body, timeout=30)
    r.raise_for_status()
    data = r.json()

    out = data.get("output_text")
    if out:
        return json.loads(out)

    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text" and "text" in c:
                return json.loads(c["text"])

    return {"intent": "unknown", "entity": "", "raw": user_text}
