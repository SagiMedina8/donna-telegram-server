"""
Donna Agent — Telegram Client
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
    if len(text) > 4000:
        text = text[:4000] + "\n…(קוצר)"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    tg("sendMessage", payload)


def send_with_expand(chat_id: int, short_text: str, expand_callback_data: str):
    send(chat_id, short_text, reply_markup={
        "inline_keyboard": [[{"text": "🔎 הרחב", "callback_data": expand_callback_data}]]
    })


def send_selection(chat_id: int, header: str, items: list[dict]):
    lines = [header]
    buttons = []
    for i, item in enumerate(items[:10], 1):
        lines.append(f"{i}. {item['label']}")
        buttons.append({"text": str(i), "callback_data": item["callback_data"]})
    rows = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]
    send(chat_id, "\n".join(lines), reply_markup={"inline_keyboard": rows})


def send_approval(chat_id: int, text: str, approval_id: str):
    send(chat_id, text, reply_markup={
        "inline_keyboard": [[
            {"text": "✅ אשר", "callback_data": f"approve:{approval_id}"},
            {"text": "❌ דחה", "callback_data": f"reject:{approval_id}"},
        ]]
    })


def send_choice(chat_id: int, text: str, choices: list[dict]):
    rows = [[c] for c in choices]
    send(chat_id, text, reply_markup={"inline_keyboard": rows})


def answer_callback(callback_query_id: str, text: str = ""):
    tg("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})


# ─── Main Menu ───

def send_main_menu(chat_id: int, greeting: str = ""):
    text = greeting or "💅 <b>דונה — מה נעשה?</b>\nבחר קטגוריה או פשוט כתוב לי בצ'אט:"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "👥 אנשים", "callback_data": "menu:people"},
                {"text": "📅 פגישות", "callback_data": "menu:meetings"},
                {"text": "📋 משימות", "callback_data": "menu:tasks"},
            ],
            [
                {"text": "📊 סטטוס יום", "callback_data": "menu:today"},
                {"text": "❓ עזרה", "callback_data": "menu:help"},
            ],
        ]
    }
    send(chat_id, text, reply_markup=keyboard)


def send_sub_menu(chat_id: int, category: str):
    menus = {
        "people": {
            "text": "<b>👥 אנשים</b>\nמה תרצה לעשות?",
            "buttons": [
                [
                    {"text": "🔍 חפש אדם", "callback_data": "action:search_person"},
                    {"text": "➕ הוסף אדם", "callback_data": "action:add_person"},
                ],
                [
                    {"text": "➕ הוסף כמה אנשים", "callback_data": "action:add_people_batch"},
                ],
                [{"text": "🔙 חזרה", "callback_data": "menu:back"}],
            ]
        },
        "meetings": {
            "text": "<b>📅 פגישות</b>\nמה תרצה לעשות?",
            "buttons": [
                [
                    {"text": "📅 היום", "callback_data": "action:today"},
                    {"text": "📅 מחר", "callback_data": "action:tomorrow"},
                ],
                [
                    {"text": "🔍 חפש פגישה", "callback_data": "action:search_meeting"},
                    {"text": "➕ פגישה חדשה", "callback_data": "action:add_meeting"},
                ],
                [{"text": "🔙 חזרה", "callback_data": "menu:back"}],
            ]
        },
        "tasks": {
            "text": "<b>📋 משימות</b>\nמה תרצה לעשות?",
            "buttons": [
                [
                    {"text": "📋 משימות פתוחות", "callback_data": "action:open_tasks"},
                    {"text": "📋 משימות היום", "callback_data": "action:today_tasks"},
                ],
                [
                    {"text": "➕ משימה חדשה", "callback_data": "action:add_task"},
                ],
                [{"text": "🔙 חזרה", "callback_data": "menu:back"}],
            ]
        },
    }
    menu = menus.get(category)
    if menu:
        send(chat_id, menu["text"], reply_markup={"inline_keyboard": menu["buttons"]})
