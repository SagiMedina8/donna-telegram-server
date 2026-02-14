"""
Donna Agent — Configuration
All environment variables, constants, and DB mappings.
"""
import os

# ---------- Telegram ----------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

# ---------- Notion ----------
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_PEOPLE_DB_ID = os.environ.get("NOTION_PEOPLE_DB_ID", "")
NOTION_MEETINGS_DB_ID = os.environ.get("NOTION_MEETINGS_DB_ID", "")
NOTION_PROJECTS_DB_ID = os.environ.get("NOTION_PROJECTS_DB_ID", "")
NOTION_DONNA_INBOX_DB_ID = os.environ.get("NOTION_DONNA_INBOX_DB_ID", "")

NOTION_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# ---------- OpenAI ----------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE = "https://api.openai.com/v1"

# ---------- Timezone ----------
TIMEZONE = "Asia/Jerusalem"

# ---------- DB name mapping (Hebrew-friendly) ----------
DB_NAME_MAP = {
    "people": NOTION_PEOPLE_DB_ID,
    "אנשים": NOTION_PEOPLE_DB_ID,
    "meetings": NOTION_MEETINGS_DB_ID,
    "פגישות": NOTION_MEETINGS_DB_ID,
    "projects": NOTION_PROJECTS_DB_ID,
    "פרויקטים": NOTION_PROJECTS_DB_ID,
    "inbox": NOTION_DONNA_INBOX_DB_ID,
}

# ---------- Allowed fields for LLM updates (People DB) ----------
ALLOWED_PEOPLE_FIELDS = [
    "טיפים להכנה",
    "הערות אישיות",
    "תחביבים ותחומי עניין",
    "אופן עבודה מועדף",
    "הערות רגישות",
    "תחום",
    "תפקיד",
    "מחלקה",
    "מנהל ישיר",
]

# ---------- Startup validation ----------
def validate_env():
    """Returns list of missing critical env vars."""
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not NOTION_TOKEN:
        missing.append("NOTION_TOKEN")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    return missing
