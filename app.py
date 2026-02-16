"""
Donna Agent — Main Application v2
"""
import os
from flask import Flask, request
import commands
import state
from config import validate_env, OWNER_CHAT_ID

app = Flask(__name__)

missing = validate_env()
if missing:
    print(f"⚠️  Missing env vars: {', '.join(missing)}")

COMMAND_MAP = {
    "/start":        (commands.cmd_start,          False),
    "/מי":          (commands.cmd_who,             True),
    "/היום":        (commands.cmd_today,            False),
    "/מחר":        (commands.cmd_tomorrow,         False),
    "/פגישה":      (commands.cmd_meeting,          True),
    "/משימות":     (commands.cmd_my_tasks,         True),
    "/סיכום":      (commands.cmd_digest,           True),
    "/אדם_חדש":   (lambda cid, t: commands.handle_create(cid, "person", t),  True),
    "/פגישה_חדשה": (lambda cid, t: commands.handle_create(cid, "meeting", t), True),
    "/משימה_חדשה": (lambda cid, t: commands.handle_create(cid, "task", t),    True),
    "/עזרה":       (commands.cmd_help,             False),
    "/סטטוס":      (commands.cmd_status,           False),
    "/schema":      (commands.cmd_schema,           True),
    "/chatid":      (commands.cmd_chatid,           False),
    "/help":        (commands.cmd_help,             False),
    "/status":      (commands.cmd_status,           False),
    "/digest":      (commands.cmd_digest,           True),
    "/tasks":       (commands.cmd_my_tasks,         True),
}


def route_command(chat_id: int, text: str) -> bool:
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

    if "callback_query" in update:
        cq = update["callback_query"]
        data = cq.get("data", "")
        chat_id = cq["message"]["chat"]["id"]
        callback_id = cq["id"]
        commands.handle_callback(callback_id, data, chat_id)
        return {"ok": True}

    msg = update.get("message")
    if not msg:
        return {"ok": True}

    chat_id = msg["chat"]["id"]
    message_id = msg.get("message_id")

    if state.is_duplicate(chat_id, message_id):
        return {"ok": True}

    text = (msg.get("text") or "").strip()
    if not text:
        return {"ok": True}

    if text.startswith("/"):
        if not route_command(chat_id, text):
            commands.cmd_help(chat_id)
        return {"ok": True}

    commands.handle_natural_text(chat_id, text)
    return {"ok": True}


@app.get("/cron/morning")
def cron_morning():
    if OWNER_CHAT_ID:
        commands.send_morning_brief(OWNER_CHAT_ID)
    return {"ok": True}

@app.get("/cron/followup")
def cron_followup():
    if OWNER_CHAT_ID:
        commands.check_ended_meetings(OWNER_CHAT_ID)
    return {"ok": True}

@app.get("/")
def health():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
