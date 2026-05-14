#!/usr/bin/env python3
import argparse
import logging
import sys
from datetime import datetime, timedelta
import litellm

from src.config import (
    MAX_EMAILS_PER_RUN,
    LLM_MODEL,
    LLM_API_KEY,
    FOLLOWUP_DAYS_1,
    FOLLOWUP_DAYS_2,
    FOLLOWUP_DAYS_3,
    YOUR_NAME,
    PROMPTS_DIR,
    LOGS_DIR,
)
from src.notion_api import (
    get_rows_to_send,
    get_all_rows_for_status,
    update_sent,
)
from src.email_sender import send_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "outreach.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def get_last_contacted_date(row):
    props = row["properties"]
    last_contacted = props.get("Last Contacted", {}).get("date")
    if last_contacted and last_contacted.get("start"):
        return datetime.strptime(last_contacted["start"], "%Y-%m-%d").date()
    return None


def get_followup_count(row):
    props = row["properties"]
    return props.get("Follow-up Count", {}).get("number", 0)


def get_status(row):
    props = row["properties"]
    status = props.get("Status", {}).get("select")
    return status.get("name") if status else None


def is_followup_due(row, followup_stage):
    last_contacted = get_last_contacted_date(row)
    if not last_contacted:
        return False

    days_since = (datetime.now().date() - last_contacted).days

    if followup_stage == 1:
        return days_since >= FOLLOWUP_DAYS_1
    elif followup_stage == 2:
        return days_since >= FOLLOWUP_DAYS_2
    elif followup_stage == 3:
        return days_since >= FOLLOWUP_DAYS_3

    return False


def get_followup_prompt(stage):
    stage_map = {1: "followup_1.txt", 2: "followup_2.txt", 3: "followup_3.txt"}
    prompt_file = PROMPTS_DIR / stage_map.get(stage, "followup_1.txt")

    if not prompt_file.exists():
        logger.error(f"Prompt file {prompt_file} not found")
        return None

    with open(prompt_file, "r") as f:
        return f.read()


def generate_followup_email(row, followup_stage):
    props = row["properties"]
    name = props.get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", "")
    company = (
        props.get("Company", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
    )
    job_title = (
        props.get("Job Title", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
    )

    prompt_template = get_followup_prompt(followup_stage)
    if not prompt_template:
        return None

    prompt = prompt_template.format(
        your_name=YOUR_NAME,
        company=company,
        job_title=job_title,
        contact_name=name,
    )

    try:
        response = litellm.completion(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=LLM_API_KEY,
            temperature=0.7,
        )
        body = response["choices"][0]["message"]["content"].strip()
        return body
    except Exception as e:
        logger.error(f"Failed to generate follow-up email: {e}")
        return None


def send_initial_emails(dry_run=False):
    try:
        rows = get_rows_to_send()
        logger.info(f"Found {len(rows)} rows ready to send")
    except Exception as e:
        logger.error(f"Failed to query Notion: {e}")
        return 0

    sent = 0
    for row in rows[:MAX_EMAILS_PER_RUN]:
        props = row["properties"]
        page_id = row["id"]

        email = props.get("HR Email", {}).get("email")
        subject = (props.get("Subject", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")
        body = (props.get("Email Body", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")
        name = props.get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", "")
        company = (props.get("Company", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")
        resume = (props.get("Resume Used", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")

        if not email or not subject or not body:
            logger.warning(f"Row {page_id} ({name} at {company}) missing email/subject/body")
            continue

        logger.info(f"Sending to {email} ({name} at {company}) with resume: {resume}")

        if dry_run:
            logger.info(f"[DRY RUN] Would send to {email}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Resume: {resume}")
            logger.info(f"Body: {body[:100]}...")
        else:
            if send_email(email, subject, body, resume_filename=resume):
                try:
                    update_sent(page_id, followup_count=0)
                    sent += 1
                    logger.info(f"Sent and updated row {page_id}")
                except Exception as e:
                    logger.error(f"Failed to update Notion for {page_id}: {e}")
            else:
                logger.error(f"Failed to send email to {email}")

    return sent


def send_followups(dry_run=False):
    sent = 0

    for status_name, followup_stage in [
        ("Emailed", 1),
        ("Follow-up 1", 2),
        ("Follow-up 2", 3),
    ]:
        try:
            rows = get_all_rows_for_status(status_name)
            logger.info(f"Found {len(rows)} rows with status {status_name}")
        except Exception as e:
            logger.error(f"Failed to query Notion: {e}")
            continue

        for row in rows:
            page_id = row["id"]
            props = row["properties"]

            if not is_followup_due(row, followup_stage):
                continue

            email = props.get("HR Email", {}).get("email")
            name = props.get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", "")
            company = (
                props.get("Company", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
            )

            if not email:
                logger.warning(f"Row {page_id} ({name}) has no HR Email")
                continue

            body = generate_followup_email(row, followup_stage)
            if not body:
                logger.error(f"Failed to generate follow-up email for {page_id}")
                continue

            subject = f"Following up: {props.get('Job Title', {}).get('rich_text', [{}])[0].get('text', {}).get('content', 'Job Application')}"

            logger.info(f"Sending follow-up {followup_stage} to {email} ({name} at {company})")

            if dry_run:
                logger.info(f"[DRY RUN] Would send follow-up {followup_stage} to {email}")
                logger.info(f"Body: {body[:100]}...")
            else:
                if send_email(email, subject, body):
                    try:
                        update_sent(page_id, followup_count=followup_stage)
                        sent += 1
                        logger.info(f"Sent follow-up {followup_stage} to {email}, updated row {page_id}")
                    except Exception as e:
                        logger.error(f"Failed to update Notion for {page_id}: {e}")
                else:
                    logger.error(f"Failed to send follow-up to {email}")

    return sent


def print_status():
    statuses = [
        "Pending",
        "Draft",
        "Emailed",
        "Follow-up 1",
        "Follow-up 2",
        "Follow-up 3",
        "Responded",
        "Paused",
        "On Hold",
        "Archived",
    ]

    try:
        for status in statuses:
            rows = get_all_rows_for_status(status)
            print(f"{status}: {len(rows)}")
    except Exception as e:
        logger.error(f"Failed to query Notion: {e}")


def main():
    parser = argparse.ArgumentParser(description="Send emails and manage follow-ups")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print pipeline summary",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without sending",
    )

    args = parser.parse_args()

    logger.info("Starting send_emails.py")

    if args.status:
        print_status()
        return

    initial_sent = send_initial_emails(dry_run=args.dry_run)
    logger.info(f"Sent {initial_sent} initial emails")

    followup_sent = send_followups(dry_run=args.dry_run)
    logger.info(f"Sent {followup_sent} follow-up emails")

    logger.info("Done")


if __name__ == "__main__":
    main()
