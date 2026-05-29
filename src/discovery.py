import json
import logging
from pathlib import Path

from src.router import classify
from src.notion_api import job_url_exists, add_discovered_job

logger = logging.getLogger(__name__)

SEARCH_DATA_DIR = Path(__file__).parent.parent / "data" / "searches"


def find_search_files(search_dir: Path = None) -> list[Path]:
    """Return search JSON files sorted newest-first."""
    target = search_dir or SEARCH_DATA_DIR
    if not target.exists():
        return []
    return sorted(target.glob("search-*.json"), reverse=True)


def load_search_file(path: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return data.get("results", []) if isinstance(data, dict) else data


def push_to_notion(jobs: list[dict], dry_run: bool = False) -> tuple[int, int]:
    """Push discovered jobs to Notion. Returns (added, skipped)."""
    added = skipped = 0

    for job in jobs:
        url = job.get("url", "")

        if not dry_run and job_url_exists(url):
            logger.debug(f"Already exists, skipping: {job.get('title')} at {job.get('company')}")
            skipped += 1
            continue

        path, platform = classify(url, job.get("applyMethod", ""))

        skill_match_raw = job.get("skillMatch", "")
        skill_match = None
        if skill_match_raw:
            if "strong" in skill_match_raw.lower():
                skill_match = "Strong"
            elif "partial" in skill_match_raw.lower():
                skill_match = "Partial"
            elif "weak" in skill_match_raw.lower():
                skill_match = "Weak"

        payload = {
            "title": job.get("title", "Unknown Role"),
            "company": job.get("company", ""),
            "job_url": url,
            "source": job.get("source", "Manual"),
            "score": job.get("score"),
            "skill_match": skill_match,
            "matched_skills": ", ".join(job.get("matchedSkills", [])),
            "path": path,
            "apply_platform": platform,
        }

        if dry_run:
            logger.info(
                f"[DRY RUN] {payload['title']} at {payload['company']} "
                f"| {path} via {platform} | score={payload['score']}"
            )
            added += 1
        else:
            try:
                add_discovered_job(payload)
                logger.info(f"Added: {payload['title']} at {payload['company']} ({path})")
                added += 1
            except Exception as e:
                logger.error(f"Failed to add {payload['title']} at {payload['company']}: {e}")

    return added, skipped
