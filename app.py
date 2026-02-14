import os
import json
import uuid
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# אחסון זמני של בקשות אישור (MVP). בהמשך נעבור ל-DB.
PENDING = {}  # approval_id -> {"chat_id": int, "action": str}

def tg(method: str, payload: dict):
    r = requests.post(f"{BASE}/{method}", json=payload, timeout=20)
    r.raise_for_status()
    return r.json()

def send_message(chat_id: int, text: str, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    tg("sendMessage", payload)

def answer_callback_query(callback_query_id: str, text: str = ""):
    tg("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})

@app.post("/telegram")
def telegram_webhook():
    update = request.get_json(silent=True) or {}

    # 1) לחיצות על כפתורים (Approve/Reject)
    if "callback_query" in update:
        cq = update["callback_query"]
        data = cq.get("data", "")  # "approve:<id>" / "reject:<id>"
        chat_id = cq["message"]["chat"]["id"]
        callback_id = cq["id"]

        if ":" not in data:
            answer_callback_query(callback_id, "משהו השתבש")
            return {"ok": True}

        action, approval_id = data.split(":", 1)
        item = PENDING.pop(approval_id, None)

        if not item:
            answer_callback_query(callback_id, "הבקשה כבר טופלה/לא נמצאה")
            send_message(chat_id, "הבקשה כבר טופלה או לא נמצאה.")
            return {"ok": True}

        if action == "approve":
            answer_callback_query(callback_id, "אושר")
            send_message(chat_id, f"אושר ✅\nפעולה: {item['action']}")
        else:
            answer_callback_query(callback_id, "נדחה")
            send_message(chat_id, f"נדחה ❌\nפעולה: {item['action']}")

        return {"ok": True}

    # 2) הודעות רגילות
    msg = update.get("message")
    if not msg:
        return {"ok": True}

    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    # דמו: יצירת בקשת אישור
    if text == "/approve_demo":
        approval_id = str(uuid.uuid4())[:8]
        action_text = "עדכון עתידי ל-Notion: הוספת תחום עניין 'Open Banking' ליואב"

        PENDING[approval_id] = {"chat_id": chat_id, "action": action_text}

        send_message(
            chat_id,
            f"דונה מבקשת אישור:\n{action_text}",
            reply_markup={
                "inline_keyboard": [
                    [
                        {"text": "אשר", "callback_data": f"approve:{approval_id}"},
                        {"text": "דחה", "callback_data": f"reject:{approval_id}"},
                    ]
                ]
            },
        )
        return {"ok": True}

    # ברירת מחדל: echo
    send_message(chat_id, f"דונה קיבלה: {text}\n(שלח /approve_demo כדי לראות אישור בטלגרם)")
    return {"ok": True}

@app.get("/")
def health():
    return "OK"
