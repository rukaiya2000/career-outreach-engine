import json
import os
from pathlib import Path
import pdfplumber
import litellm
from src.config import RESUMES_DIR, DATA_DIR, LLM_MODEL, LLM_API_KEY


CACHE_FILE = DATA_DIR / "resume_cache.json"


def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def extract_resume_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text.strip()


def get_resume_cache(refresh: bool = False):
    if refresh:
        cache = {}
    else:
        cache = load_cache()

    resumes = {}
    if not RESUMES_DIR.exists():
        return resumes

    for pdf_file in RESUMES_DIR.glob("*.pdf"):
        file_key = pdf_file.name
        mtime = os.path.getmtime(pdf_file)
        cache_key = f"{file_key}:{mtime}"

        if cache_key not in cache:
            print(f"Extracting {pdf_file.name}...")
            text = extract_resume_text(str(pdf_file))
            cache[cache_key] = text

        resumes[pdf_file.name] = cache[cache_key]

    save_cache(cache)
    return resumes


def select_resume(jd_text: str, resumes: dict) -> tuple[str, str]:
    if not resumes:
        raise ValueError("No resumes found in resumes/ directory")

    resume_list = "\n".join(
        f"{i+1}. {name}" for i, name in enumerate(resumes.keys())
    )

    prompt = f"""You are helping someone apply for a job. Given the job description below and multiple resumes, pick the BEST resume that matches the role.

Job Description:
{jd_text}

Available Resumes:
{resume_list}

Respond with ONLY:
RESUME: <number>
REASON: <one sentence explaining why this resume is the best match>

Do not include any other text."""

    response = litellm.completion(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        api_key=LLM_API_KEY,
        temperature=0.3,
    )

    response_text = response["choices"][0]["message"]["content"].strip()
    lines = response_text.split("\n")

    resume_num = None
    reason = ""
    for line in lines:
        if line.startswith("RESUME:"):
            try:
                resume_num = int(line.replace("RESUME:", "").strip()) - 1
            except ValueError:
                pass
        elif line.startswith("REASON:"):
            reason = line.replace("REASON:", "").strip()

    if resume_num is None or resume_num < 0 or resume_num >= len(resumes):
        resume_num = 0

    selected_resume = list(resumes.keys())[resume_num]
    return selected_resume, reason
