"""
Donna Agent — Configuration
"""
import os
import random

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_PEOPLE_DB_ID = os.environ.get("NOTION_PEOPLE_DB_ID", "")
NOTION_MEETINGS_DB_ID = os.environ.get("NOTION_MEETINGS_DB_ID", "")
NOTION_PROJECTS_DB_ID = os.environ.get("NOTION_PROJECTS_DB_ID", "")
NOTION_DONNA_INBOX_DB_ID = os.environ.get("NOTION_DONNA_INBOX_DB_ID", "")
NOTION_TASKS_DB_ID = os.environ.get("NOTION_TASKS_DB_ID", "")
NOTION_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE = "https://api.openai.com/v1"
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", "0"))
TIMEZONE = "Asia/Jerusalem"

DB_NAME_MAP = {
    "people": NOTION_PEOPLE_DB_ID, "אנשים": NOTION_PEOPLE_DB_ID,
    "meetings": NOTION_MEETINGS_DB_ID, "פגישות": NOTION_MEETINGS_DB_ID,
    "projects": NOTION_PROJECTS_DB_ID, "פרויקטים": NOTION_PROJECTS_DB_ID,
    "inbox": NOTION_DONNA_INBOX_DB_ID,
    "tasks": NOTION_TASKS_DB_ID, "משימות": NOTION_TASKS_DB_ID,
}

ALLOWED_PEOPLE_FIELDS = [
    "טיפים להכנה", "הערות אישיות", "תחביבים ותחומי עניין",
    "אופן עבודה מועדף", "הערות רגישות", "תחום", "תפקיד",
    "מחלקה", "מנהל ישיר",
]

DONNA_QUOTES = {
    "morning": [
        "☀️ בוקר טוב! אם זה חשוב — נמצא דרך.",
        "🌅 בוקר! תן לי את ההקשר — ואני אביא פתרון.",
        "☕ בוקר טוב! לא הכול דחוף, אבל הכול מחושב.",
        "🔥 בוקר! מי שמכיר את הסוף, בוחר התחלה אחרת.",
    ],
    "followup": [
        "📝 הפגישה הסתיימה. מה היה? אנשים מספרים הכול — צריך לדעת איך להסתכל.",
        "🎯 סיימת? ספר לי — אני אסדר את הכל.",
        "✏️ מה יצא מהפגישה? תכתוב בקצרה ואני אעשה סדר.",
    ],
    "approval": [
        "✅ בוצע. חכמה שקטה מנצחת רעש.",
        "✅ עשוי. מקצוענות היא לעשות נכון גם כשלא מסתכלים.",
        "✅ נעשה. תוצאות מדברות.",
    ],
    "rejection": [
        "❌ בסדר, ביטלתי. לפעמים המהלך הכי חכם הוא לא לזוז.",
        "❌ נדחה. אל תתבלבל בין לחץ לחשיבות.",
    ],
    "creation": [
        "🆕 נוצר! כוח אמיתי לא צועק — הוא מזיז.",
        "✨ הוספתי! עבודה טובה נראית טבעית — אבל לא מקרית.",
        "🎯 מוכן! סטנדרט גבוה חוסך ויכוחים.",
    ],
    "greeting": [
        "היי! 👋 אני דונה. מה בתוכנית?",
        "שלום! 😊 מה אפשר לסדר?",
        "מה קורה? 💫 אני פה, תגיד מה צריך.",
    ],
    "thanks": [
        "בכיף! 😊 בשביל זה אני פה.",
        "אין בעד מה! 💪 סמוך עליי — זה מה שאני עושה.",
    ],
    "wisdom": [
        "💡 תחשוב שני צעדים קדימה — ואז עוד אחד.",
        "🎯 היחסים קובעים את התוצאה יותר מהטיעון.",
        "🧩 פתרון טוב היום יכול להיות בעיה מחר.",
        "🔥 אם זה היה פשוט, כבר היו מסיימים.",
        "⚡ מי שממהר — כבר הפסיד קלף.",
        "🧠 אינטואיציה היא ניסיון שעובד מהר.",
    ],
    "no_results": [
        "🔍 לא מצאתי כלום. בוא ננסה אחרת.",
        "📭 ריק פה. אולי תנסה שם אחר?",
    ],
    "error": [
        "😕 משהו השתבש. קודם מייצבים — אחר כך פותרים.",
        "🔧 שגיאה. אל תדאג, כבר ראיתי גרוע מזה.",
    ],
}

def donna_says(category: str) -> str:
    quotes = DONNA_QUOTES.get(category, DONNA_QUOTES["wisdom"])
    return random.choice(quotes)

def validate_env():
    missing = []
    if not TELEGRAM_TOKEN: missing.append("TELEGRAM_TOKEN")
    if not NOTION_TOKEN: missing.append("NOTION_TOKEN")
    if not OPENAI_API_KEY: missing.append("OPENAI_API_KEY")
    return missing
