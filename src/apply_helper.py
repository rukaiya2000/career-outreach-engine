#!/usr/bin/env python3
"""
CLI helper for the /job-apply skill.

Commands:
  get-jobs                        Print approved Direct Apply rows as JSON
  select-resume --page-id <id>    Pick best resume for a Notion row's JD
  mark-applied --page-id <id> --resume <filename>  Update Notion to Applied
"""
import argparse
import json
import sys

from src.config import RESUMES_DIR


def cmd_get_jobs():
    from src.notion_api import get_approved_direct_apply_rows

    rows = get_approved_direct_apply_rows()
    jobs = []
    for row in rows:
        props = row["properties"]
        jobs.append({
            "page_id": row["id"],
            "job_url": props.get("Job URL", {}).get("url", ""),
            "company": (props.get("Company", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", ""),
            "job_title": (props.get("Job Title", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", ""),
            "jd_text": (props.get("Job Description Text", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", ""),
        })
    print(json.dumps(jobs, indent=2))


def cmd_select_resume(page_id: str):
    from src.notion_api import get_page
    from src.resume_selector import get_resume_cache, select_resume
    from src.jd_scraper import scrape

    page = get_page(page_id)
    props = page["properties"]

    jd_text = (props.get("Job Description Text", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")

    if not jd_text.strip():
        job_url = props.get("Job URL", {}).get("url", "")
        if job_url:
            try:
                jd_text = scrape(job_url)
            except Exception as e:
                print(json.dumps({"error": f"Could not scrape JD: {e}"}))
                sys.exit(1)

    if not jd_text.strip():
        print(json.dumps({"error": "No job description text available"}))
        sys.exit(1)

    resumes = get_resume_cache()
    if not resumes:
        print(json.dumps({"error": "No resumes found in resumes/ directory"}))
        sys.exit(1)

    selected, reason = select_resume(jd_text, resumes)
    print(json.dumps({
        "resume": selected,
        "reason": reason,
        "resume_path": str(RESUMES_DIR / selected),
    }))


def cmd_mark_applied(page_id: str, resume: str):
    from src.notion_api import update_applied

    update_applied(page_id, resume_used=resume)
    print(f"Marked {page_id} as Applied (resume: {resume})")


def main():
    parser = argparse.ArgumentParser(description="Helper for /job-apply skill")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("get-jobs", help="List approved Direct Apply rows from Notion")

    p_resume = sub.add_parser("select-resume", help="Pick best resume for a Notion row")
    p_resume.add_argument("--page-id", required=True)

    p_mark = sub.add_parser("mark-applied", help="Mark a row as Applied in Notion")
    p_mark.add_argument("--page-id", required=True)
    p_mark.add_argument("--resume", required=True)

    args = parser.parse_args()

    if args.cmd == "get-jobs":
        cmd_get_jobs()
    elif args.cmd == "select-resume":
        cmd_select_resume(args.page_id)
    elif args.cmd == "mark-applied":
        cmd_mark_applied(args.page_id, args.resume)


if __name__ == "__main__":
    main()
