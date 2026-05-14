from datetime import datetime
from typing import Optional
from notion_client import Client
from src.config import NOTION_API_KEY, NOTION_DATABASE_ID

client = Client(auth=NOTION_API_KEY)


def get_pending_rows():
    response = client.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={"property": "Status", "select": {"equals": "Pending"}},
    )
    return response.get("results", [])


def get_rows_to_send():
    response = client.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "and": [
                {"property": "Status", "select": {"equals": "Draft"}},
                {"property": "Approved", "checkbox": {"equals": True}},
            ]
        },
    )
    return response.get("results", [])


def get_rows_for_followup():
    response = client.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "and": [
                {
                    "property": "Status",
                    "select": {
                        "equals": "Emailed"
                    },
                },
            ]
        },
    )
    emailed = response.get("results", [])

    followup_response = client.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "Status",
            "select": {"does_not_equal": "Pending"},
        },
    )
    all_rows = followup_response.get("results", [])

    skip_statuses = {"Responded", "Paused", "On Hold", "Archived"}
    followup_rows = []
    for row in all_rows:
        status = row["properties"]["Status"]["select"]["name"]
        if status in {"Emailed", "Follow-up 1", "Follow-up 2"}:
            if status not in skip_statuses:
                followup_rows.append(row)

    return followup_rows


def update_draft(page_id: str, subject: str, body: str, resume_used: str):
    client.pages.update(
        page_id=page_id,
        properties={
            "Subject": {"title": [{"text": {"content": subject}}]},
            "Email Body": {"rich_text": [{"text": {"content": body}}]},
            "Resume Used": {"rich_text": [{"text": {"content": resume_used}}]},
            "Status": {"select": {"name": "Draft"}},
        },
    )


def update_sent(page_id: str, followup_count: int = 0):
    status_map = {
        0: "Emailed",
        1: "Follow-up 1",
        2: "Follow-up 2",
        3: "Follow-up 3",
    }
    status = status_map.get(followup_count, "Follow-up 3")

    client.pages.update(
        page_id=page_id,
        properties={
            "Status": {"select": {"name": status}},
            "Last Contacted": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
            "Follow-up Count": {"number": followup_count},
        },
    )


def get_page_property(page_id: str, property_name: str):
    page = client.pages.retrieve(page_id)
    return page["properties"].get(property_name, {})


def get_all_rows_for_status(*statuses):
    rows = []
    for status in statuses:
        response = client.databases.query(
            database_id=NOTION_DATABASE_ID,
            filter={"property": "Status", "select": {"equals": status}},
        )
        rows.extend(response.get("results", []))
    return rows
