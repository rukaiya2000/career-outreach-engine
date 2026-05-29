# Job Automation Pipeline

An end-to-end job application automation system that combines AI-powered job discovery, smart routing, cold outreach email generation, and ATS form-filling into a single pipeline tracked through Notion.

## What it does

1. **Discover** — `/job-search` scrapes LinkedIn, Hacker News, and Twitter for matching roles, scores them against your skills, and pushes results directly into Notion
2. **Route** — each job is automatically classified as **Direct Apply** (LinkedIn Easy Apply, Greenhouse, Ashby, Lever, Workday, Rippling) or **Cold Outreach**
3. **Apply** — for Direct Apply rows, `/job-apply` auto-fills ATS forms using browser automation
4. **Outreach** — for Cold Outreach rows, the pipeline drafts a personalized email, you approve in Notion, and it sends with automatic follow-ups

Notion is the single dashboard — every job, every status, every email lives there.

---

## Architecture

```
/job-search  ──▶  pipeline.py discover  ──▶  Notion (Discovered)
                                                    │
                          ┌─────────────────────────┤
                          │                         │
                   Direct Apply               Cold Outreach
                          │                         │
                   /job-apply                pipeline.py draft
                   (fills form)              (LLM writes email)
                          │                         │
                   Status: Applied          You approve in Notion
                                                    │
                                            pipeline.py send
                                            (Gmail + follow-ups)
```

---

## Pipeline CLI

```bash
# Push latest /job-search results into Notion
python pipeline.py discover

# Push from a specific search file
python pipeline.py discover --from-search data/searches/search-2026-05-29.json

# Draft cold outreach emails for all Pending rows
python pipeline.py draft

# Send approved drafts + any scheduled follow-ups
python pipeline.py send

# Show full pipeline summary
python pipeline.py status

# Full pipeline in one shot: discover → draft → send
python pipeline.py run

# Any command with --dry-run previews without making changes
python pipeline.py run --dry-run
```

---

## Claude Code Skills

Three skills live in `skills/` and are invoked directly in Claude Code:

| Skill | Command | Description |
|-------|---------|-------------|
| Job Preferences | `/job-preferences` | Set target titles, salary floor, remote preference — saved to `claude-job-profile.json` |
| Job Search | `/job-search` | Search LinkedIn, HN, Twitter — scores results, saves JSON, auto-runs `pipeline.py discover` |
| Job Apply | `/job-apply` | Browser automation to fill ATS forms on LinkedIn, Greenhouse, Ashby, Lever, Workday, Rippling |

### To install skills in Claude Code

```bash
# From the project root
claude skills add ./skills/job-preferences
claude skills add ./skills/job-search
claude skills add ./skills/job-apply
```

---

## Notion Database Schema

The unified DB tracks both apply paths:

| Column | Type | Purpose |
|--------|------|---------|
| Name | Title | Contact name (or role title for direct apply) |
| Company | Text | Company name |
| Job Title | Text | Role title |
| Job URL | URL | Direct link to job posting |
| Job Description URL | URL | JD page (scraped for email drafting) |
| Path | Select | `Direct Apply` or `Cold Outreach` |
| Apply Platform | Select | LinkedIn / Greenhouse / Ashby / Lever / Workday / Rippling |
| Source | Select | LinkedIn / HN / Twitter / Manual |
| Score | Number | 0–100 relevance score from `/job-search` |
| Skill Match | Select | Strong / Partial / Weak |
| Matched Skills | Text | Skills from your profile found in the JD |
| HR Email | Email | Recipient for cold outreach |
| Subject | Text | LLM-written, editable |
| Email Body | Text | LLM-written, editable |
| Resume Used | Text | Which PDF was attached |
| Status | Select | Discovered → Pending → Draft → Applied / Emailed → Follow-up 1/2/3 → Responded |
| Approved | Checkbox | Tick to approve email for sending |
| Last Contacted | Date | Auto-set on send |
| Follow-up Count | Number | Auto-incremented |
| Outcome | Select | Interview / Offer / Rejected |
| Notes | Text | Freeform |

---

## Setup

### 1. Install dependencies

```bash
uv sync
# or
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in `.env`:

| Variable | Where to get it |
|----------|----------------|
| `NOTION_API_KEY` | [notion.so/my-integrations](https://www.notion.so/my-integrations) |
| `NOTION_DATABASE_ID` | From your database URL |
| `EMAIL_ADDRESS` | Your Gmail address |
| `EMAIL_APP_PASSWORD` | [Generate App Password](https://myaccount.google.com/apppasswords) (requires 2FA) |
| `LLM_API_KEY` | Your Anthropic / OpenAI API key |
| `YOUR_NAME` | Used in email templates |

### 3. Add resumes

```bash
cp ~/Documents/resume.pdf resumes/
```

### 4. Create Notion database

**New database:**
```bash
python src/setup_notion.py "https://www.notion.so/Your-Page-abc123"
# Copy the printed NOTION_DATABASE_ID into .env
```

**Migrate an existing database** (adds the new discovery columns):
```bash
python src/setup_notion.py --migrate-discovery "https://www.notion.so/your-db-url"
```

### 5. Set up your profile

Run `/job-preferences` in Claude Code to set your target titles, salary floor, and remote preference. These are saved to `claude-job-profile.json` and used by both `/job-search` and `/job-apply`.

---

## Cold Outreach Details

### How emails are drafted

For each `Pending` + `Cold Outreach` row in Notion:

1. Scrapes the job description from the URL (or uses pasted text)
2. Selects the best-matching resume from `resumes/` using the LLM
3. Optionally uses few-shot examples from your previously approved emails
4. Generates subject + body, writes them back to Notion (status → Draft)

You review and edit inline in Notion, then tick **Approved**.

### Follow-up schedule

| Stage | Timing (default) | Prompt |
|-------|-----------------|--------|
| Follow-up 1 | Day 4 | Gentle nudge |
| Follow-up 2 | Day 8 | New hook (project/achievement) |
| Follow-up 3 | Day 14 | Graceful close |

Configure timing in `.env` with `FOLLOWUP_DAYS_1`, `FOLLOWUP_DAYS_2`, `FOLLOWUP_DAYS_3`.

### Prompt templates

All prompts are plain text in `src/prompts/` — edit to adjust tone and style:

- `initial_email.txt`
- `followup_1.txt`, `followup_2.txt`, `followup_3.txt`

---

## LLM Configuration

```bash
# Anthropic (default)
MODEL_PROVIDER=anthropic
MODEL_NAME=claude-sonnet-4-6

# OpenAI
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o

# Custom endpoint (e.g. Navigator AI at UF)
MODEL_PROVIDER=openai
MODEL_NAME=gpt-oss-120b
LLM_BASE_URL=https://api.ai.it.ufl.edu
```

---

## Logging

Activity logs to `logs/pipeline.log` and `logs/outreach.log`, plus stdout.

---

## Troubleshooting

**"No search JSON files found"** — Run `/job-search` in Claude Code first. It saves to `data/searches/` automatically.

**"No resumes found"** — Make sure PDFs are in `resumes/` (not in subdirectories).

**"Failed to scrape JD"** — The page may be JS-heavy. Paste the job description into the Notion cell instead.

**"Notion API error"** — Check `NOTION_API_KEY` and `NOTION_DATABASE_ID` in `.env`. Make sure the integration has been shared with your database.

**"Gmail auth failed"** — Use an App Password (not your regular password). Requires 2FA to be enabled on your Google account.

---

## Attribution

Browser automation skills (`/job-apply`, `/job-search`, `/job-preferences`) are adapted from [neonwatty/job-apply-plugin](https://github.com/neonwatty/job-apply-plugin) by Jeremy Watt, licensed under [MIT](https://github.com/neonwatty/job-apply-plugin/blob/main/LICENSE).
