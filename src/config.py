import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "anthropic")
MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-4-5")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = f"{MODEL_PROVIDER}/{MODEL_NAME}"

FOLLOWUP_DAYS_1 = int(os.getenv("FOLLOWUP_DAYS_1", "4"))
FOLLOWUP_DAYS_2 = int(os.getenv("FOLLOWUP_DAYS_2", "8"))
FOLLOWUP_DAYS_3 = int(os.getenv("FOLLOWUP_DAYS_3", "14"))
MAX_EMAILS_PER_RUN = int(os.getenv("MAX_EMAILS_PER_RUN", "20"))
YOUR_NAME = os.getenv("YOUR_NAME", "")

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
RESUMES_DIR = PROJECT_ROOT / "resumes"
PROMPTS_DIR = PROJECT_ROOT / "src" / "prompts"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
RESUMES_DIR.mkdir(exist_ok=True)
