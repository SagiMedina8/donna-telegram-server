"""
Donna Agent — Main Application
Flask webhook routes and command routing.
"""
import os
from flask import Flask, request
import commands
import state
from config import validate_env

app = Flask(__name__)

# ─── Startup validation ───
missing = validate_env()
if missing:
    print(f"⚠️  Missing env vars: {', '.join(missing)}")
    print("The server will start but some features won't work.")

# ─── Command routing table (Hebrew) ───
# Maps command prefix -> (handler_function, needs_argument)
COMMAND_MAP = {
    "/מי":      (commands.cmd_who,      True),
    "/היום":    (commands.cmd_today,     False),
    "/מחר":    (commands.cmd_tomorrow,  False),
    "/פגישה":  (commands.cmd_meeting,   True),
    "/סיכום":  (commands.cmd_digest,    True),
    "/עזרה":   (commands.cmd_help,      False),
    "/סטטוס":  (commands.cmd_status,    False),
    "/schema":  (commands.cmd_schema,    True),
    "/chatid":  (commands.cmd_chatid,   False),
    # aliases
    "/help":    (commands.cmd_help,      False),
    "/status":  (commands.cmd_status,    False),
    "/digest":  (commands.cmd_digest,    True),
}


def route_command(chat_id: int, text: str):
    """Parse message text and call the right command handler."""
    # Try each command prefix
    for prefix, (handler, needs_arg) in COMMAND_MAP.items():
        if text == prefix or text.startswith(prefix + " ") or text.startswith(prefix + "\n"):
            if needs_arg:
                arg = text[len(prefix):].strip()
                handler(chat_id, arg)
            else:
                handler(chat_id)
            return True
    return False


@app.post("/telegram")
def telegram_webhook():
    update = request.get_json(silent=True) or {}

    # ─── A) Button clicks ───
    if "callback_query" in update:
        cq = update["callback_query"]
        data = cq.get("data", "")
        chat_id = cq["message"]["chat"]["id"]
        callback_id = cq["id"]
        commands.handle_callback(callback_id, data, chat_id)
        return {"ok": True}

    # ─── B) Messages ───
    msg = update.get("message")
    if not msg:
        return {"ok": True}

    chat_id = msg["chat"]["id"]
    message_id = msg.get("message_id")

    # Dedup
    if state.is_duplicate(chat_id, message_id):
        return {"ok": True}

    text = (msg.get("text") or "").strip()
    if not text:
        return {"ok": True}

    # Try to match a command
    if not route_command(chat_id, text):
        # Default: show help
        commands.cmd_help(chat_id)

    return {"ok": True}


@app.get("/")
def health():
    return "OK"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
