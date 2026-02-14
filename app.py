import os
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def send_message(chat_id: int, text: str):
    r = requests.post(f"{BASE}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=20)
    r.raise_for_status()

@app.post("/telegram")
def telegram_webhook():
    update = request.get_json(silent=True) or {}
    msg = update.get("message")
    if not msg:
        return {"ok": True}

    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    send_message(chat_id, f"דונה קיבלה: {text}")
    return {"ok": True}

@app.get("/")
def health():
    return "OK"
