# Career Outreach Engine

A CLI tool that automates personalized job outreach emails. Notion is the single interface — no terminal prompts.

## How it works

### Step 1: Draft emails

```bash
python src/draft_emails.py
```

For each **Pending** row in your Notion database:
- Scrapes the job description from the URL
- Loads your resume PDFs
- Calls Claude to pick the best resume and write a personalized email
- Writes the draft subject and body back to Notion
- Sets status to **Draft**

You then open Notion, read and edit the draft inline, and check **Approved** to send.

### Step 2: Send emails

```bash
python src/send_emails.py
```

Sends all **Draft + Approved** rows exactly as written in Notion. Also handles automatic follow-ups:
- Follow-up 1 after 4 days (default)
- Follow-up 2 after 8 days
- Follow-up 3 after 14 days

## Setup

### 1. Install dependencies

```bash
uv add notion-client litellm pdfplumber requests beautifulsoup4 python-dotenv lxml
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

Required values:
- `NOTION_API_KEY` — Get from [Notion Integrations](https://www.notion.so/my-integrations)
- `NOTION_DATABASE_ID` — From your database URL
- `EMAIL_ADDRESS` — Your Gmail
- `EMAIL_APP_PASSWORD` — [Generate here](https://myaccount.google.com/apppasswords) (requires 2FA)
- `LLM_API_KEY` — Your Anthropic API key
- `YOUR_NAME` — Used in email templates

### 3. Add resumes

Place your resume PDFs in the `resumes/` directory:

```bash
mkdir resumes
cp ~/Documents/*.pdf resumes/
```

### 4. Create Notion database

**Option A: Automatic (recommended)**

Create an empty page in Notion, then run:

```bash
python src/setup_notion.py "https://www.notion.so/Your-Page-Name-abc123"
```

The script will:
- Create a child database with all required columns
- Print the `NOTION_DATABASE_ID`
- Copy that ID to `.env`

**Option B: Manual**

Create a new Notion database with these columns:

| Column | Type | Description |
|--------|------|-------------|
| Name | Title | HR contact name |
| Company | Text | Company name |
| HR Email | Email | Recipient |
| Job Title | Text | Role applied for |
| Job Description URL | URL | Scraped by draft_emails.py |
| Subject | Text | Written by LLM, editable |
| Email Body | Text | Written by LLM, editable |
| Resume Used | Text | Selected by LLM |
| Status | Select | Pending, Draft, Emailed, Follow-up 1/2/3, Responded, Paused, On Hold, Archived |
| Approved | Checkbox | Tick to approve for sending |
| Last Contacted | Date | Auto-set on send |
| Follow-up Count | Number | Auto-incremented |
| Outcome | Select | Interview, Offer, Rejected |
| Notes | Text | Manual notes |

Copy your database ID from the URL (the long hex string) and add to `.env`.

## Usage

### Draft emails

```bash
# Draft all pending rows
python src/draft_emails.py

# Rebuild resume cache (if you added/changed resumes)
python src/draft_emails.py --refresh-resumes

# Overwrite existing drafts
python src/draft_emails.py --reprocess

# Preview without writing to Notion
python src/draft_emails.py --dry-run
```

### Send emails

```bash
# Send all approved drafts and handle due follow-ups
python src/send_emails.py

# See pipeline summary
python src/send_emails.py --status

# Preview without sending
python src/send_emails.py --dry-run
```

## How drafts are generated

The tool uses Claude to:

1. **Select the best resume** from your PDFs based on the job description
2. **Write the subject line** referencing a specific skill/achievement
3. **Write personalized email body** with:
   - Reference to something specific about the company/role
   - Why your experience is a match
   - Clear call-to-action

All placeholders in prompts are automatically filled:
- `{contact_name}` — HR contact
- `{company}` — Company name
- `{job_title}` — Job title
- `{your_name}` — Your name from `.env`

## Follow-ups

Once an email is sent (status = **Emailed**), follow-ups send automatically on schedule:

- **Follow-up 1** (day 4): Gentle nudge
- **Follow-up 2** (day 8): New hook (project or achievement)
- **Follow-up 3** (day 14): Short graceful close

Each stage has 3-4 template variants; Claude picks and personalizes one.

Rows with status **Responded**, **Paused**, **On Hold**, or **Archived** are always skipped.

## Prompt templates

All prompts are plain text in `src/prompts/`:

- `initial_email.txt` — Select resume, write subject and body
- `followup_1.txt` — 3-4 gentle nudge variants
- `followup_2.txt` — 3-4 new hook variants
- `followup_3.txt` — 3-4 graceful close variants

Edit these files to customize the email tone/style. Placeholders are filled at runtime.

## Logging

All activity logs to `logs/outreach.log` and stdout.

## Troubleshooting

**"No resumes found"** — Make sure PDFs are in `resumes/` directory and not in subdirectories.

**"Failed to scrape JD"** — The job posting page may be JavaScript-heavy. Copy and paste the job description into the Notion cell instead.

**"Notion API error"** — Check that your `NOTION_API_KEY` and `NOTION_DATABASE_ID` are correct.

**"Gmail auth failed"** — Ensure you generated an App Password (not your regular password) and have 2FA enabled.

**"LLM error"** — Verify your `LLM_API_KEY` is valid and you have quota available.

## LLM Configuration

The tool is configured to use Claude by default, but you can change the model:

```bash
# In .env
MODEL_PROVIDER=anthropic
MODEL_NAME=claude-sonnet-4-5  # or claude-opus-4-7, etc.
```

The tool uses LiteLLM, which supports any provider (OpenAI, Anthropic, etc.).
