from urllib.parse import urlparse

PLATFORM_PATTERNS = {
    "linkedin.com": "LinkedIn",
    "boards.greenhouse.io": "Greenhouse",
    "jobs.ashbyhq.com": "Ashby",
    "jobs.lever.co": "Lever",
    "myworkdayjobs.com": "Workday",
    "rippling.com": "Rippling",
}


def classify(url: str, apply_method: str = "") -> tuple[str, str]:
    """Return (path, platform). path is 'Direct Apply' or 'Cold Outreach'."""
    if not url:
        return "Cold Outreach", "Unknown"

    try:
        hostname = urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return "Cold Outreach", "Unknown"

    for pattern, platform in PLATFORM_PATTERNS.items():
        if pattern in hostname:
            return "Direct Apply", platform

    if apply_method and "easy apply" in apply_method.lower():
        return "Direct Apply", "LinkedIn"

    return "Cold Outreach", "Unknown"
