import logging
import requests
from datetime import datetime
from src.config import NOTION_API_KEY, NOTION_DATABASE_ID

BASE_URL = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

NOTION_RICH_TEXT_LIMIT = 2000

logger = logging.getLogger(__name__)


def _query(filter_body: dict) -> list:
    results = []
    body = {"filter": filter_body, "page_size": 100}
    while True:
        resp = requests.post(
            f"{BASE_URL}/databases/{NOTION_DATABASE_ID}/query",
            headers=HEADERS,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        body["start_cursor"] = data["next_cursor"]
    return results


def _update(page_id: str, properties: dict):
    resp = requests.patch(
        f"{BASE_URL}/pages/{page_id}",
        headers=HEADERS,
        json={"properties": properties},
    )
    resp.raise_for_status()
    return resp.json()


def get_pending_rows() -> list:
    return _query({"property": "Status", "select": {"equals": "Pending"}})


def get_rows_to_send() -> list:
    return _query({
        "and": [
            {"property": "Status", "select": {"equals": "Draft"}},
            {"property": "Approved", "checkbox": {"equals": True}},
        ]
    })


def get_all_rows_for_status(*statuses) -> list:
    rows = []
    for status in statuses:
        rows.extend(_query({"property": "Status", "select": {"equals": status}}))
    return rows


def get_rows_for_followup() -> list:
    rows = []
    for status in ("Emailed", "Follow-up 1", "Follow-up 2"):
        rows.extend(_query({"property": "Status", "select": {"equals": status}}))
    return rows


def get_approved_examples() -> list:
    """Return rows where Approved=True and Email Body is non-empty."""
    rows = _query({"property": "Approved", "checkbox": {"equals": True}})
    examples = []
    for row in rows:
        props = row["properties"]
        body = (props.get("Email Body", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")
        if body.strip():
            examples.append(row)
    return examples


def update_draft(page_id: str, subject: str, body: str, resume_used: str):
    _update(page_id, {
        "Subject": {"rich_text": [{"text": {"content": subject}}]},
        "Email Body": {"rich_text": [{"text": {"content": body}}]},
        "Resume Used": {"rich_text": [{"text": {"content": resume_used}}]},
        "Status": {"select": {"name": "Draft"}},
    })


def store_jd_text(page_id: str, jd_text: str):
    """Write scraped JD text back to Notion (truncated to Notion's rich_text limit)."""
    if len(jd_text) > NOTION_RICH_TEXT_LIMIT:
        logger.warning(f"JD text truncated from {len(jd_text)} to {NOTION_RICH_TEXT_LIMIT} chars for Notion storage")
        jd_text = jd_text[:NOTION_RICH_TEXT_LIMIT]
    _update(page_id, {
        "Job Description Text": {"rich_text": [{"text": {"content": jd_text}}]},
    })


def update_sent(page_id: str, followup_count: int = 0):
    status_map = {0: "Emailed", 1: "Follow-up 1", 2: "Follow-up 2", 3: "Follow-up 3"}
    _update(page_id, {
        "Status": {"select": {"name": status_map.get(followup_count, "Follow-up 3")}},
        "Last Contacted": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
        "Follow-up Count": {"number": followup_count},
    })


def job_url_exists(url: str) -> bool:
    """Return True if a row with this Job URL already exists (deduplication)."""
    if not url:
        return False
    try:
        rows = _query({"property": "Job URL", "url": {"equals": url}})
        return len(rows) > 0
    except Exception:
        return False


def add_discovered_job(payload: dict):
    """Create a new Notion row for a freshly discovered job."""
    properties: dict = {
        "Name": {"title": [{"text": {"content": payload.get("title", "Unknown Role")[:2000]}}]},
        "Company": {"rich_text": [{"text": {"content": payload.get("company", "")[:2000]}}]},
        "Job Title": {"rich_text": [{"text": {"content": payload.get("title", "")[:2000]}}]},
        "Status": {"select": {"name": "Discovered"}},
    }

    optional_select = {
        "Path": payload.get("path"),
        "Source": payload.get("source"),
        "Apply Platform": payload.get("apply_platform"),
        "Skill Match": payload.get("skill_match"),
    }
    for key, val in optional_select.items():
        if val:
            properties[key] = {"select": {"name": val}}

    if payload.get("job_url"):
        properties["Job URL"] = {"url": payload["job_url"]}
        properties["Job Description URL"] = {"url": payload["job_url"]}
    if payload.get("score") is not None:
        properties["Score"] = {"number": float(payload["score"])}
    if payload.get("matched_skills"):
        properties["Matched Skills"] = {
            "rich_text": [{"text": {"content": payload["matched_skills"][:2000]}}]
        }

    resp = requests.post(
        f"{BASE_URL}/pages",
        headers=HEADERS,
        json={"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties},
    )
    resp.raise_for_status()
    return resp.json()


def get_page(page_id: str) -> dict:
    resp = requests.get(f"{BASE_URL}/pages/{page_id}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def get_approved_direct_apply_rows() -> list:
    return _query({
        "and": [
            {"property": "Approved", "checkbox": {"equals": True}},
            {"property": "Path", "select": {"equals": "Direct Apply"}},
        ]
    })


def update_applied(page_id: str, resume_used: str = ""):
    """Mark a Direct Apply row as Applied after the user submits the form."""
    props = {
        "Status": {"select": {"name": "Applied"}},
        "Approved": {"checkbox": False},
        "Last Contacted": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
    }
    if resume_used:
        props["Resume Used"] = {"rich_text": [{"text": {"content": resume_used}}]}
    _update(page_id, props)
