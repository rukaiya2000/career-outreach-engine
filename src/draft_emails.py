#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path
import litellm

from src.config import (
    MAX_EMAILS_PER_RUN,
    LLM_MODEL,
    LLM_API_KEY,
    PROMPTS_DIR,
    LOGS_DIR,
    YOUR_NAME,
    EMAIL_MAX_WORDS,
)
from src.notion_api import get_pending_rows, update_draft, store_jd_text
from src.jd_scraper import scrape
from src.resume_selector import get_resume_cache, select_resume
from src.few_shot import get_few_shot_examples, format_few_shot_section

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "outreach.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def parse_initial_email_response(response_text: str) -> dict:
    lines = response_text.split("\n")
    result = {"resume": None, "subject": None, "body": None}

    for i, line in enumerate(lines):
        if line.startswith("RESUME_NUMBER:"):
            try:
                result["resume"] = int(line.replace("RESUME_NUMBER:", "").strip()) - 1
            except ValueError:
                pass
        elif line.startswith("SUBJECT:"):
            result["subject"] = line.replace("SUBJECT:", "").strip()
        elif line.startswith("BODY:"):
            body_lines = []
            for j in range(i + 1, len(lines)):
                if not lines[j].startswith("RESUME_NUMBER:"):
                    body_lines.append(lines[j])
            result["body"] = "\n".join(body_lines).strip()
            break

    return result


def draft_email_for_row(row, resumes, dry_run=False):
    page_id = row["id"]
    props = row["properties"]

    name = props.get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", "")
    company = (
        props.get("Company", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
    )
    job_title = (
        props.get("Job Title", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
    )
    jd_url = props.get("Job Description URL", {}).get("url", "")
    jd_text_manual = (
        (props.get("Job Description Text", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")
    )

    logger.info(f"Processing: {name} at {company} for {job_title}")

    if jd_url:
        try:
            jd_text = scrape(jd_url)
            logger.info("Scraped job description from URL")
        except Exception as e:
            logger.warning(f"Failed to scrape JD from {jd_url}: {e}. Falling back to pasted text.")
            jd_text = jd_text_manual
    else:
        jd_text = jd_text_manual

    if not jd_text.strip():
        logger.warning(f"Row {page_id} ({name} at {company}) has no JD URL or text. Skipping.")
        return False

    if not dry_run:
        try:
            store_jd_text(page_id, jd_text)
        except Exception as e:
            logger.warning(f"Failed to store JD text in Notion: {e}")

    if not resumes:
        resumes = get_resume_cache()

    if not resumes:
        logger.error("No resumes found. Please add PDFs to resumes/ directory.")
        return False

    try:
        selected_resume, reason = select_resume(jd_text, resumes)
        logger.info(f"Selected resume: {selected_resume} ({reason})")
    except Exception as e:
        logger.error(f"Failed to select resume: {e}")
        return False

    resume_list = "\n".join(f"{i+1}. {name}" for i, name in enumerate(resumes.keys()))

    examples = get_few_shot_examples(jd_text)
    few_shot_section = format_few_shot_section(examples)

    prompt_file = PROMPTS_DIR / "initial_email.txt"
    with open(prompt_file, "r") as f:
        prompt_template = f.read()

    prompt = prompt_template.format(
        your_name=YOUR_NAME,
        company=company,
        job_title=job_title,
        contact_name=name,
        resumes_list=resume_list,
        job_description=jd_text,
        num_resumes=len(resumes),
        max_words=EMAIL_MAX_WORDS,
        few_shot_section=few_shot_section,
    )

    try:
        response = litellm.completion(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_key=LLM_API_KEY,
            temperature=0.7,
        )
        response_text = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return False

    parsed = parse_initial_email_response(response_text)

    if not parsed["subject"] or not parsed["body"]:
        logger.error(f"Failed to parse email response: {response_text}")
        return False

    word_count = len(parsed["body"].split())
    if word_count > EMAIL_MAX_WORDS:
        logger.warning(f"Body has {word_count} words (limit is {EMAIL_MAX_WORDS}). Consider editing in Notion.")

    logger.info(f"Generated subject: {parsed['subject']}")

    return {
        "page_id": page_id,
        "subject": parsed["subject"],
        "body": parsed["body"],
        "resume": selected_resume,
    }


def main():
    parser = argparse.ArgumentParser(description="Draft emails from Pending Notion rows")
    parser.add_argument(
        "--refresh-resumes",
        action="store_true",
        help="Rebuild resume cache",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Overwrite existing drafts",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing to Notion",
    )

    args = parser.parse_args()

    logger.info("Starting draft_emails.py")

    try:
        resumes = get_resume_cache(refresh=args.refresh_resumes)
        logger.info(f"Loaded {len(resumes)} resumes")
    except Exception as e:
        logger.error(f"Failed to load resumes: {e}")
        sys.exit(1)

    try:
        pending_rows = get_pending_rows()
        logger.info(f"Found {len(pending_rows)} pending rows")
    except Exception as e:
        logger.error(f"Failed to query Notion: {e}")
        sys.exit(1)

    processed = 0
    for row in pending_rows[:MAX_EMAILS_PER_RUN]:
        result = draft_email_for_row(row, resumes, dry_run=args.dry_run)

        if result:
            if args.dry_run:
                logger.info(f"[DRY RUN] Would update row {result['page_id']}")
                logger.info(f"Subject: {result['subject']}")
                logger.info(f"Body preview: {result['body'][:100]}...")
            else:
                try:
                    update_draft(
                        result["page_id"],
                        result["subject"],
                        result["body"],
                        result["resume"],
                    )
                    logger.info(f"Updated row {result['page_id']} with draft")
                    processed += 1
                except Exception as e:
                    logger.error(f"Failed to update Notion: {e}")

    logger.info(f"Drafted {processed} emails")


if __name__ == "__main__":
    main()
