import logging
import random
from src.config import FEW_SHOT_MODE, FEW_SHOT_N, FEW_SHOT_K
from src.notion_api import get_approved_examples

logger = logging.getLogger(__name__)


def _extract_example(row: dict) -> dict | None:
    props = row["properties"]
    company = (props.get("Company", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")
    job_title = (props.get("Job Title", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")
    subject = (props.get("Subject", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")
    body = (props.get("Email Body", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")
    jd_text = (props.get("Job Description Text", {}).get("rich_text") or [{}])[0].get("text", {}).get("content", "")

    if not subject or not body:
        return None

    return {
        "page_id": row["id"],
        "company": company,
        "job_title": job_title,
        "subject": subject,
        "body": body,
        "jd_text": jd_text,
    }


def _random_selection(examples: list, n: int) -> list:
    return random.sample(examples, min(n, len(examples)))


def _similarity_selection(current_jd: str, examples: list, k: int) -> list:
    from src.embeddings import get_embedding, get_cached_embedding, cosine_similarity

    try:
        current_embedding = get_embedding(current_jd)
    except Exception as e:
        logger.warning(f"Failed to embed current JD, falling back to random: {e}")
        return _random_selection(examples, k)

    scored = []
    for ex in examples:
        if not ex["jd_text"].strip():
            continue
        try:
            ex_embedding = get_cached_embedding(ex["page_id"], ex["jd_text"])
            score = cosine_similarity(current_embedding, ex_embedding)
            scored.append((score, ex))
        except Exception as e:
            logger.warning(f"Failed to embed example {ex['page_id']}: {e}")

    if not scored:
        logger.warning("No embeddable examples found, falling back to random")
        return _random_selection(examples, k)

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [ex for _, ex in scored[:k]]
    logger.info(f"Top-{k} similarity scores: {[round(s, 3) for s, _ in scored[:k]]}")
    return top


def get_few_shot_examples(current_jd: str) -> list:
    if FEW_SHOT_MODE == "none":
        return []

    try:
        rows = get_approved_examples()
    except Exception as e:
        logger.warning(f"Could not fetch approved examples for few-shot: {e}")
        return []

    examples = [e for e in (_extract_example(r) for r in rows) if e]

    if not examples:
        logger.info("No approved examples found for few-shot")
        return []

    if FEW_SHOT_MODE == "random":
        selected = _random_selection(examples, FEW_SHOT_N)
        logger.info(f"Found {len(selected)} few-shot examples (random):")
        for ex in selected:
            logger.info(f"  - {ex['company']} | {ex['job_title']} | Subject: {ex['subject']}")
        return selected

    if FEW_SHOT_MODE == "similarity":
        selected = _similarity_selection(current_jd, examples, FEW_SHOT_K)
        logger.info(f"Found {len(selected)} few-shot examples (similarity):")
        for ex in selected:
            logger.info(f"  - {ex['company']} | {ex['job_title']} | Subject: {ex['subject']}")
        return selected

    logger.warning(f"Unknown FEW_SHOT_MODE '{FEW_SHOT_MODE}', skipping few-shot")
    return []


def format_few_shot_section(examples: list) -> str:
    if not examples:
        return ""

    lines = ["Here are examples of previously approved emails for reference — use them as style guides, do not copy them:\n"]
    for i, ex in enumerate(examples, 1):
        lines.append(f"Example {i} — {ex['company']} ({ex['job_title']}):")
        lines.append(f"Subject: {ex['subject']}")
        lines.append(f"Body:\n{ex['body']}")
        lines.append("---")

    return "\n".join(lines)
