#!/usr/bin/env python3
import sys
import re
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_VERSION = "2022-06-28"


def headers():
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def extract_page_id(url: str) -> str:
    patterns = [
        r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})',
        r'([a-f0-9]{32})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            raw = match.group(1).replace("-", "")
            return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    raise ValueError(f"Could not extract page ID from URL: {url}")


def setup_database(parent_page_id: str):
    if not NOTION_API_KEY:
        print("Error: NOTION_API_KEY not set in .env")
        sys.exit(1)

    print(f"Creating database under page {parent_page_id}...")

    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": "Job Outreach"}}],
        "properties": {
            "Name": {"title": {}},
            "Company": {"rich_text": {}},
            "HR Email": {"email": {}},
            "Job Title": {"rich_text": {}},
            "Job Description URL": {"url": {}},
            "Subject": {"rich_text": {}},
            "Email Body": {"rich_text": {}},
            "Resume Used": {"rich_text": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "Pending", "color": "blue"},
                        {"name": "Draft", "color": "yellow"},
                        {"name": "Emailed", "color": "green"},
                        {"name": "Follow-up 1", "color": "orange"},
                        {"name": "Follow-up 2", "color": "orange"},
                        {"name": "Follow-up 3", "color": "orange"},
                        {"name": "Responded", "color": "purple"},
                        {"name": "Paused", "color": "gray"},
                        {"name": "On Hold", "color": "gray"},
                        {"name": "Archived", "color": "default"},
                    ]
                }
            },
            "Approved": {"checkbox": {}},
            "Last Contacted": {"date": {}},
            "Follow-up Count": {"number": {"format": "number"}},
            "Outcome": {
                "select": {
                    "options": [
                        {"name": "Interview", "color": "blue"},
                        {"name": "Offer", "color": "green"},
                        {"name": "Rejected", "color": "red"},
                    ]
                }
            },
            "Notes": {"rich_text": {}},
        },
    }

    resp = requests.post(
        "https://api.notion.com/v1/databases",
        headers=headers(),
        json=body,
    )

    if not resp.ok:
        print(f"Error: {resp.status_code} {resp.text}")
        sys.exit(1)

    data = resp.json()
    db_id = data["id"]
    columns = [k for k in data.get("properties", {}).keys()]
    print(f"  ✓ Database created: {db_id}")
    print(f"  ✓ Columns: {', '.join(columns)}")
    print(f"\nAdd this to your .env file:")
    print(f"NOTION_DATABASE_ID={db_id}\n")

    return db_id


def main():
    if len(sys.argv) < 2:
        print("Usage: python src/setup_notion.py <notion-page-url>")
        print("\nExample: python src/setup_notion.py https://www.notion.so/My-Page-abc123")
        sys.exit(1)

    page_url = sys.argv[1]

    try:
        page_id = extract_page_id(page_url)
        setup_database(page_id)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
