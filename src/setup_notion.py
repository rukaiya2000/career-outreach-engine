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
        "title": [{"type": "text", "text": {"content": "Job Automation Pipeline"}}],
        "properties": {
            "Name": {"title": {}},
            "Sr No.": {"unique_id": {}},
            "Company": {"rich_text": {}},
            "Job Title": {"rich_text": {}},
            "HR Email": {"email": {}},
            "Job URL": {"url": {}},
            "Job Description URL": {"url": {}},
            "Job Description Text": {"rich_text": {}},
            "Path": {
                "select": {
                    "options": [
                        {"name": "Cold Outreach", "color": "blue"},
                        {"name": "Direct Apply", "color": "green"},
                    ]
                }
            },
            "Apply Platform": {
                "select": {
                    "options": [
                        {"name": "LinkedIn", "color": "blue"},
                        {"name": "Greenhouse", "color": "green"},
                        {"name": "Ashby", "color": "purple"},
                        {"name": "Lever", "color": "orange"},
                        {"name": "Workday", "color": "red"},
                        {"name": "Rippling", "color": "yellow"},
                        {"name": "Other", "color": "gray"},
                        {"name": "Unknown", "color": "default"},
                    ]
                }
            },
            "Source": {
                "select": {
                    "options": [
                        {"name": "LinkedIn", "color": "blue"},
                        {"name": "HN", "color": "orange"},
                        {"name": "Twitter", "color": "gray"},
                        {"name": "Manual", "color": "default"},
                    ]
                }
            },
            "Score": {"number": {"format": "number"}},
            "Skill Match": {
                "select": {
                    "options": [
                        {"name": "Strong", "color": "green"},
                        {"name": "Partial", "color": "yellow"},
                        {"name": "Weak", "color": "red"},
                    ]
                }
            },
            "Matched Skills": {"rich_text": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "Discovered", "color": "default"},
                        {"name": "Pending", "color": "blue"},
                        {"name": "Draft", "color": "yellow"},
                        {"name": "Applied", "color": "green"},
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
            "Subject": {"rich_text": {}},
            "Email Body": {"rich_text": {}},
            "Resume Used": {"rich_text": {}},
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
            "Last Contacted": {"date": {}},
            "Created Date": {"created_time": {}},
            "Last Edited": {"last_edited_time": {}},
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


def migrate_add_discovery_columns(db_id_or_url: str):
    """Add discovery columns (Job URL, Path, Source, Score, etc.) to an existing database."""
    if not NOTION_API_KEY:
        print("Error: NOTION_API_KEY not set in .env")
        sys.exit(1)

    try:
        db_id = extract_page_id(db_id_or_url)
    except ValueError:
        db_id = db_id_or_url.strip()

    print(f"Adding discovery columns to database {db_id}...")

    new_properties = {
        "Job URL": {"url": {}},
        "Path": {
            "select": {
                "options": [
                    {"name": "Cold Outreach", "color": "blue"},
                    {"name": "Direct Apply", "color": "green"},
                ]
            }
        },
        "Apply Platform": {
            "select": {
                "options": [
                    {"name": "LinkedIn", "color": "blue"},
                    {"name": "Greenhouse", "color": "green"},
                    {"name": "Ashby", "color": "purple"},
                    {"name": "Lever", "color": "orange"},
                    {"name": "Workday", "color": "red"},
                    {"name": "Rippling", "color": "yellow"},
                    {"name": "Other", "color": "gray"},
                    {"name": "Unknown", "color": "default"},
                ]
            }
        },
        "Source": {
            "select": {
                "options": [
                    {"name": "LinkedIn", "color": "blue"},
                    {"name": "HN", "color": "orange"},
                    {"name": "Twitter", "color": "gray"},
                    {"name": "Manual", "color": "default"},
                ]
            }
        },
        "Score": {"number": {"format": "number"}},
        "Skill Match": {
            "select": {
                "options": [
                    {"name": "Strong", "color": "green"},
                    {"name": "Partial", "color": "yellow"},
                    {"name": "Weak", "color": "red"},
                ]
            }
        },
        "Matched Skills": {"rich_text": {}},
    }

    resp = requests.patch(
        f"https://api.notion.com/v1/databases/{db_id}",
        headers=headers(),
        json={"properties": new_properties},
    )

    if not resp.ok:
        print(f"Error: {resp.status_code} {resp.text}")
        sys.exit(1)

    added = list(new_properties.keys())
    print(f"  ✓ Added columns: {', '.join(added)}")
    print("\nNote: Also add 'Discovered' and 'Applied' options to your Status select in Notion manually.")


def migrate_add_unique_id(db_id_or_url: str):
    """Add a Row ID (unique_id) property to an existing Notion database."""
    if not NOTION_API_KEY:
        print("Error: NOTION_API_KEY not set in .env")
        sys.exit(1)

    try:
        db_id = extract_page_id(db_id_or_url)
    except ValueError:
        db_id = db_id_or_url.strip()

    print(f"Adding 'Row ID' (unique_id) property to database {db_id}...")

    resp = requests.patch(
        f"https://api.notion.com/v1/databases/{db_id}",
        headers=headers(),
        json={"properties": {"Row ID": {"unique_id": {}}}},
    )

    if not resp.ok:
        print(f"Error: {resp.status_code} {resp.text}")
        sys.exit(1)

    print("  ✓ 'Row ID' property added. Notion will auto-assign IDs to all existing rows.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Set up or migrate the Notion Job Outreach database")
    parser.add_argument("page_url", nargs="?", help="Notion page URL to create the database under")
    parser.add_argument(
        "--migrate-id",
        metavar="DB_URL_OR_ID",
        help="Add unique_id 'Row ID' column to an existing database",
    )
    parser.add_argument(
        "--migrate-discovery",
        metavar="DB_URL_OR_ID",
        help="Add discovery columns (Job URL, Path, Source, Score, etc.) to an existing database",
    )

    args = parser.parse_args()

    if args.migrate_id:
        migrate_add_unique_id(args.migrate_id)
    elif args.migrate_discovery:
        migrate_add_discovery_columns(args.migrate_discovery)
    elif args.page_url:
        try:
            page_id = extract_page_id(args.page_url)
            setup_database(page_id)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
