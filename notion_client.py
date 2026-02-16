"""
Donna Agent — Notion Client
"""
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from config import (
    NOTION_TOKEN, NOTION_BASE, NOTION_VERSION,
    NOTION_PEOPLE_DB_ID, NOTION_MEETINGS_DB_ID,
    NOTION_PROJECTS_DB_ID, NOTION_TASKS_DB_ID,
    NOTION_DONNA_INBOX_DB_ID, DB_NAME_MAP, TIMEZONE,
)

def _headers():
    return {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"}

def _tz():
    return ZoneInfo(TIMEZONE)

def _post(url, body):
    r = requests.post(url, headers=_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def _get(url):
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()

def _patch(url, body):
    r = requests.patch(url, headers=_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def retrieve_database(database_id: str) -> dict:
    return _get(f"{NOTION_BASE}/databases/{database_id}")

def get_schema(db_name: str) -> dict | None:
    db_id = DB_NAME_MAP.get(db_name.strip().lower(), "")
    if not db_id: return None
    db = retrieve_database(db_id)
    return {name: meta.get("type") for name, meta in db.get("properties", {}).items()}

def get_page(page_id: str) -> dict:
    return _get(f"{NOTION_BASE}/pages/{page_id}")

def extract_prop(page: dict, prop_name: str) -> str:
    props = page.get("properties", {})
    prop = props.get(prop_name, {})
    ptype = prop.get("type", "")
    if ptype == "title":
        return "".join(x.get("plain_text", "") for x in prop.get("title", []))
    if ptype == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop.get("rich_text", []))
    if ptype == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    if ptype == "multi_select":
        return ", ".join(s.get("name", "") for s in prop.get("multi_select", []))
    if ptype == "checkbox":
        return "כן" if prop.get("checkbox") else "לא"
    if ptype == "date":
        d = prop.get("date")
        if not d: return ""
        return d.get("start", "") + (" → " + d["end"] if d.get("end") else "")
    if ptype == "number":
        return str(prop.get("number", ""))
    if ptype == "status":
        s = prop.get("status")
        return s.get("name", "") if s else ""
    if ptype == "people":
        return ", ".join(p.get("name", "") for p in prop.get("people", []))
    if ptype == "relation":
        return f"({len(prop.get('relation', []))} קשרים)"
    return ""


# ── People ──

def query_people(name: str, limit: int = 10) -> list[dict]:
    body = {"page_size": limit, "filter": {"property": "שם", "title": {"contains": name}}}
    return _post(f"{NOTION_BASE}/databases/{NOTION_PEOPLE_DB_ID}/query", body).get("results", [])

def get_person_card(page: dict, full: bool = False) -> dict:
    short = ["שם", "תפקיד", "מחלקה", "תחום"]
    all_f = ["שם", "תפקיד", "מחלקה", "תחום", "מנהל ישיר", "אופן עבודה מועדף",
             "תחביבים ותחומי עניין", "טיפים להכנה", "הערות אישיות", "הערות רגישות",
             "פרוייקטים", "Meetings", "פעיל", "לייבלים"]
    fields = all_f if full else short
    return {f: extract_prop(page, f) for f in fields if extract_prop(page, f)}

def update_person_field(page_id: str, field_name: str, new_text: str):
    body = {"properties": {field_name: {"rich_text": [{"type": "text", "text": {"content": new_text}}]}}}
    return _patch(f"{NOTION_BASE}/pages/{page_id}", body)

def create_person(name: str, fields: dict | None = None) -> dict:
    props = {"שם": {"title": [{"type": "text", "text": {"content": name}}]}}
    for fname, val in (fields or {}).items():
        if val:
            props[fname] = {"rich_text": [{"type": "text", "text": {"content": val}}]}
    return _post(f"{NOTION_BASE}/pages", {"parent": {"database_id": NOTION_PEOPLE_DB_ID}, "properties": props})


# ── Meetings ──

def query_meetings_by_date(date_str: str) -> list[dict]:
    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    body = {
        "page_size": 25,
        "filter": {"and": [
            {"property": "תאריך", "date": {"on_or_after": date_str}},
            {"property": "תאריך", "date": {"before": next_day}},
        ]},
        "sorts": [{"property": "תאריך", "direction": "ascending"}],
    }
    return _post(f"{NOTION_BASE}/databases/{NOTION_MEETINGS_DB_ID}/query", body).get("results", [])

def query_meetings_by_text(search_text: str, limit: int = 10) -> list[dict]:
    body = {"page_size": limit, "filter": {"property": "Name", "title": {"contains": search_text}}}
    return _post(f"{NOTION_BASE}/databases/{NOTION_MEETINGS_DB_ID}/query", body).get("results", [])

def get_meeting_card(page: dict, full: bool = False) -> dict:
    short = ["Name", "תאריך", "משתתפים", "מטרה"]
    all_f = ["Name", "תאריך", "משתתפים", "מטרה", "תובנות מרכזיות", "אפיק", "סטטוס"]
    fields = all_f if full else short
    return {f: extract_prop(page, f) for f in fields if extract_prop(page, f)}

def create_meeting(name: str, date_iso: str = "", fields: dict | None = None) -> dict:
    props = {"Name": {"title": [{"type": "text", "text": {"content": name}}]}}
    if date_iso:
        props["תאריך"] = {"date": {"start": date_iso}}
    for fname, val in (fields or {}).items():
        if val and fname not in ("Name", "תאריך"):
            props[fname] = {"rich_text": [{"type": "text", "text": {"content": val}}]}
    return _post(f"{NOTION_BASE}/pages", {"parent": {"database_id": NOTION_MEETINGS_DB_ID}, "properties": props})


# ── Tasks ──

def query_tasks_open(limit: int = 25) -> list[dict]:
    body = {"page_size": limit, "filter": {"property": "Status", "status": {"does_not_equal": "Done"}},
            "sorts": [{"property": "Due date", "direction": "ascending"}]}
    return _post(f"{NOTION_BASE}/databases/{NOTION_TASKS_DB_ID}/query", body).get("results", [])

def query_tasks_by_date(date_str: str) -> list[dict]:
    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    body = {"page_size": 25, "filter": {"and": [
        {"property": "Due date", "date": {"on_or_after": date_str}},
        {"property": "Due date", "date": {"before": next_day}},
    ]}, "sorts": [{"property": "Due date", "direction": "ascending"}]}
    return _post(f"{NOTION_BASE}/databases/{NOTION_TASKS_DB_ID}/query", body).get("results", [])

def get_task_card(page: dict) -> dict:
    fields = ["Task name", "Status", "Due date", "עדיפות", "פרוייקט", "Assignee"]
    return {f: extract_prop(page, f) for f in fields if extract_prop(page, f)}

def create_task(name: str, due_date: str = "", priority: str = "", project_id: str = "") -> dict:
    props = {"Task name": {"title": [{"type": "text", "text": {"content": name}}]}}
    if due_date: props["Due date"] = {"date": {"start": due_date}}
    if priority: props["עדיפות"] = {"rich_text": [{"type": "text", "text": {"content": priority}}]}
    if project_id: props["פרוייקט"] = {"relation": [{"id": project_id}]}
    return _post(f"{NOTION_BASE}/pages", {"parent": {"database_id": NOTION_TASKS_DB_ID}, "properties": props})


# ── Projects ──

def query_projects(name: str = "", limit: int = 25) -> list[dict]:
    body = {"page_size": limit}
    if name: body["filter"] = {"property": "Name", "title": {"contains": name}}
    return _post(f"{NOTION_BASE}/databases/{NOTION_PROJECTS_DB_ID}/query", body).get("results", [])

def find_project_id(name: str) -> str | None:
    results = query_projects(name, limit=3)
    return results[0]["id"] if results else None


# ── utility ──

def today_str() -> str:
    return datetime.now(_tz()).strftime("%Y-%m-%d")

def tomorrow_str() -> str:
    return (datetime.now(_tz()) + timedelta(days=1)).strftime("%Y-%m-%d")

def now_iso() -> str:
    return datetime.now(_tz()).isoformat()
