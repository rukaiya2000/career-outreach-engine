#!/usr/bin/env python3
"""
Job Pilot — unified CLI

Commands:
  discover   Push latest job search results from /job-search into Notion
  draft      Draft cold outreach emails for Pending rows
  send       Send approved drafts and scheduled follow-ups
  status     Show a summary of the full pipeline
  run        Full pipeline: discover → draft → send
"""
import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "logs" / "pipeline.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ── discover ──────────────────────────────────────────────────────────────────

def cmd_discover(args):
    from src.discovery import find_search_files, load_search_file, push_to_notion, SEARCH_DATA_DIR

    if args.from_search:
        search_files = [Path(args.from_search)]
    else:
        search_files = find_search_files()

    if not search_files:
        logger.warning(
            f"No search JSON files found in {SEARCH_DATA_DIR}. "
            "Run /job-search first — it will save results there automatically."
        )
        return

    files_to_process = search_files if args.all else [search_files[0]]

    total_added = total_skipped = 0
    for f in files_to_process:
        logger.info(f"Processing {f.name} ...")
        jobs = load_search_file(f)
        logger.info(f"  Found {len(jobs)} jobs")
        added, skipped = push_to_notion(jobs, dry_run=args.dry_run)
        logger.info(f"  → {added} added, {skipped} already in Notion")
        total_added += added
        total_skipped += skipped

    logger.info(f"Discover complete: {total_added} added, {total_skipped} skipped")


# ── draft ─────────────────────────────────────────────────────────────────────

def cmd_draft(args):
    from src.draft_emails import main as _draft_main

    argv = ["draft_emails.py"]
    if getattr(args, "refresh_resumes", False):
        argv.append("--refresh-resumes")
    if getattr(args, "reprocess", False):
        argv.append("--reprocess")
    if args.dry_run:
        argv.append("--dry-run")

    sys.argv = argv
    _draft_main()


# ── send ──────────────────────────────────────────────────────────────────────

def cmd_send(args):
    from src.send_emails import main as _send_main

    argv = ["send_emails.py"]
    if args.dry_run:
        argv.append("--dry-run")

    sys.argv = argv
    _send_main()


# ── add ───────────────────────────────────────────────────────────────────────

def cmd_add(args):
    from src.jd_scraper import scrape
    from src.router import classify
    from src.notion_api import job_url_exists, add_discovered_job

    url = args.url

    if not args.dry_run and job_url_exists(url):
        logger.info(f"Already in Notion: {url}")
        return

    path, platform = classify(url, "")

    payload = {
        "title": args.title or "Unknown Role",
        "company": args.company or "",
        "job_url": url,
        "source": "Manual",
        "path": path,
        "apply_platform": platform,
    }

    if args.dry_run:
        logger.info(f"[DRY RUN] Would add: {payload['title']} at {payload['company']} ({path} via {platform})")
        return

    try:
        add_discovered_job(payload)
        logger.info(f"Added: {payload['title']} at {payload['company']} ({path} via {platform})")
    except Exception as e:
        logger.error(f"Failed to add job: {e}")


# ── status ────────────────────────────────────────────────────────────────────

def cmd_status(_args):
    from src.send_emails import print_status
    print_status()


# ── run (full pipeline) ───────────────────────────────────────────────────────

def cmd_run(args):
    logger.info("=" * 50)
    logger.info("STEP 1 / 3 — Discover")
    logger.info("=" * 50)
    args.from_search = None
    args.all = False
    cmd_discover(args)

    logger.info("=" * 50)
    logger.info("STEP 2 / 3 — Draft cold outreach emails")
    logger.info("=" * 50)
    cmd_draft(args)

    logger.info("=" * 50)
    logger.info("STEP 3 / 3 — Send approved emails + follow-ups")
    logger.info("=" * 50)
    cmd_send(args)

    logger.info("Pipeline complete.")


# ── CLI wiring ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Job Automation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without making any changes")

    sub = parser.add_subparsers(dest="command", required=True)

    # discover
    p_disc = sub.add_parser("discover", help="Push /job-search results into Notion")
    p_disc.add_argument(
        "--from-search", metavar="FILE",
        help="Path to a specific search JSON file (default: latest in data/searches/)"
    )
    p_disc.add_argument("--all", action="store_true", help="Process all saved search files")
    p_disc.set_defaults(func=cmd_discover)

    # draft
    p_draft = sub.add_parser("draft", help="Draft cold outreach emails for Pending rows")
    p_draft.add_argument("--refresh-resumes", action="store_true", help="Rebuild resume cache")
    p_draft.add_argument("--reprocess", action="store_true", help="Overwrite existing drafts")
    p_draft.set_defaults(func=cmd_draft)

    # send
    p_send = sub.add_parser("send", help="Send approved drafts and scheduled follow-ups")
    p_send.set_defaults(func=cmd_send)

    # status
    p_status = sub.add_parser("status", help="Show pipeline summary")
    p_status.set_defaults(func=cmd_status)

    # add
    p_add = sub.add_parser("add", help="Add a single job URL to Notion")
    p_add.add_argument("url", help="Job posting URL")
    p_add.add_argument("--title", help="Job title (optional, used if not scrapable)")
    p_add.add_argument("--company", help="Company name (optional)")
    p_add.set_defaults(func=cmd_add)

    # run
    p_run = sub.add_parser("run", help="Full pipeline: discover → draft → send")
    p_run.add_argument("--refresh-resumes", action="store_true", help="Rebuild resume cache")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
