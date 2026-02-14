"""
Donna Agent — Telegram Client
Send messages, buttons, and handle callbacks.
"""
import json
import requests
from config import TELEGRAM_TOKEN

TG_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def tg(method: str, payload: dict) -> dict:
    r = requests.post(f"{TG_BASE}/{method}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def send(chat_id: int, text: str, reply_markup=None):
    """Send a text message, optionally with inline keyboard."""
    # Telegram limits message to 4096 chars
    if len(text) > 4000:
        text = text[:4000] + "\n…(קוצר)"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    tg("sendMessage", payload)


def send_with_expand(chat_id: int, short_text: str, expand_callback_data: str):
    """Send a short card with an 'expand' button."""
    send(
        chat_id,
        short_text,
        reply_markup={
            "inline_keyboard": [
                [{"text": "🔎 הרחב", "callback_data": expand_callback_data}]
            ]
        },
    )


def send_selection(chat_id: int, header: str, items: list[dict]):
    """
    Send a numbered list with inline buttons for selection.
    items: [{"label": "דני כהן | PM | מוצר", "callback_data": "select:..."}]
    """
    lines = [header]
    buttons = []
    for i, item in enumerate(items[:10], 1):
        lines.append(f"{i}. {item['label']}")
        buttons.append({"text": str(i), "callback_data": item["callback_data"]})

    # Arrange buttons in rows of 5
    rows = [buttons[i : i + 5] for i in range(0, len(buttons), 5)]

    send(chat_id, "\n".join(lines), reply_markup={"inline_keyboard": rows})


def send_approval(chat_id: int, text: str, approval_id: str):
    """Send a message with approve/reject buttons."""
    send(
        chat_id,
        text,
        reply_markup={
            "inline_keyboard": [
                [
                    {"text": "✅ אשר", "callback_data": f"approve:{approval_id}"},
                    {"text": "❌ דחה", "callback_data": f"reject:{approval_id}"},
                ]
            ]
        },
    )


def answer_callback(callback_query_id: str, text: str = ""):
    tg("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})
