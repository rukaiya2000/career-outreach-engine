<div align="center">
  <img src="./logo.svg" alt="JobPilot" width="380"/>
  <br/><br/>

  <p>End-to-end job application automation — discover, apply, and follow up without leaving your terminal.</p>

  ![Python](https://img.shields.io/badge/python-3.13+-blue?style=flat-square&logo=python&logoColor=white)
  ![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
  ![Claude](https://img.shields.io/badge/powered%20by-Claude-blueviolet?style=flat-square)
  ![Notion](https://img.shields.io/badge/tracked%20in-Notion-black?style=flat-square&logo=notion)

</div>

---

## Overview

JobPilot is a CLI pipeline that automates every step of the job hunt:

| Step | What happens |
|------|-------------|
| **Discover** | `/job-search` scrapes LinkedIn, Hacker News, and Twitter for roles matching your profile |
| **Route** | Each job is classified as **Direct Apply** (ATS form) or **Cold Outreach** (email) |
| **Apply** | `/job-apply` fills ATS forms on LinkedIn, Greenhouse, Ashby, Lever, Workday, and Rippling |
| **Outreach** | Claude drafts a personalized cold email; you approve it in Notion and it sends automatically |
| **Follow up** | Scheduled follow-ups at day 4, 8, and 14 — zero manual tracking |

Notion is the single dashboard. Every job, every status, every draft lives there.

---

## Architecture

```
/job-search  ──▶  pipeline.py discover  ──▶  Notion (Discovered)
                                                    │
                          ┌─────────────────────────┤
                          ▼                         ▼
                   Direct Apply               Cold Outreach
                          │                         │
                   /job-apply                pipeline.py draft
                   (browser automation)      (Claude writes email)
                          │                         │
                   Status: Applied          Approve in Notion
                                                    │
                                            pipeline.py send
                                            (Gmail + follow-ups)
```

---

## Prerequisites

- Python 3.13+
- A [Notion integration](https://www.notion.so/my-integrations) with a connected workspace
- A Gmail account with an [App Password](https://myaccount.google.com/apppasswords) (requires 2FA)
- An Anthropic or OpenAI API key

---

## Installation

```bash
git clone https://github.com/rukaiya2000/job-pilot.git
cd job-pilot

# Using uv (recommended)
uv sync

# Or pip
pip install -e .
```

---

## Configuration

```bash
cp .env.example .env
```

| Variable | Description | Where to get it |
|----------|-------------|----------------|
| `NOTION_API_KEY` | Notion integration token | [notion.so/my-integrations](https://www.notion.so/my-integrations) |
| `NOTION_DATABASE_ID` | Target database ID | From your database URL |
| `EMAIL_ADDRESS` | Your Gmail address | — |
| `EMAIL_APP_PASSWORD` | Gmail app password | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) |
| `LLM_API_KEY` | Anthropic or OpenAI key | — |
| `YOUR_NAME` | Your name (used in email templates) | — |
| `MODEL_PROVIDER` | `anthropic` or `openai` | Default: `anthropic` |
| `MODEL_NAME` | Model to use | Default: `claude-sonnet-4-6` |
| `FOLLOWUP_DAYS_1/2/3` | Follow-up intervals in days | Default: `4`, `8`, `14` |

### LLM options

```bash
# Anthropic (default)
MODEL_PROVIDER=anthropic
MODEL_NAME=claude-sonnet-4-6

# OpenAI
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o

# Custom endpoint
MODEL_PROVIDER=openai
MODEL_NAME=gpt-oss-120b
LLM_BASE_URL=https://your-endpoint.example.com
```

---

## Notion Setup

**New database:**
```bash
python src/setup_notion.py "https://www.notion.so/Your-Page-abc123"
# Prints your NOTION_DATABASE_ID — copy it into .env
```

**Migrate an existing database** (adds discovery columns):
```bash
python src/setup_notion.py --migrate-discovery "https://www.notion.so/your-db-url"
```

### Database schema

| Column | Type | Purpose |
|--------|------|---------|
| Name | Title | Contact name or role title |
| Company | Text | Company name |
| Job Title | Text | Role title |
| Job URL | URL | Direct link to posting |
| Path | Select | `Direct Apply` · `Cold Outreach` |
| Apply Platform | Select | LinkedIn · Greenhouse · Ashby · Lever · Workday · Rippling |
| Source | Select | LinkedIn · HN · Twitter · Manual |
| Score | Number | 0–100 relevance score |
| Skill Match | Select | Strong · Partial · Weak |
| Status | Select | Discovered → Pending → Draft → Applied/Emailed → Follow-up 1/2/3 → Responded |
| Approved | Checkbox | Tick to approve a cold email for sending |
| Last Contacted | Date | Auto-set on send |
| Follow-up Count | Number | Auto-incremented |
| Outcome | Select | Interview · Offer · Rejected |

---

## Usage

### Pipeline CLI

```bash
# Run the full pipeline in one shot
python pipeline.py run

# Individual steps
python pipeline.py discover                          # push /job-search results → Notion
python pipeline.py discover --from-search FILE       # use a specific search JSON
python pipeline.py draft                             # draft cold outreach emails
python pipeline.py send                              # send approved drafts + follow-ups
python pipeline.py status                            # show pipeline summary
python pipeline.py add URL --title "Role" --company "Co"  # manually add a job

# Dry run any command
python pipeline.py run --dry-run
```

### Claude Code Skills

Three skills live in `skills/` and are invoked directly in Claude Code:

```bash
# Install
claude skills add ./skills/job-preferences
claude skills add ./skills/job-search
claude skills add ./skills/job-apply
```

| Skill | Command | What it does |
|-------|---------|-------------|
| Job Preferences | `/job-preferences` | Set target titles, salary floor, remote preference |
| Job Search | `/job-search` | Search LinkedIn, HN, Twitter — scores and pushes to Notion |
| Job Apply | `/job-apply` | Browser automation to fill ATS application forms |

---

## Resumes

Place PDF resumes in the `resumes/` directory. Claude selects the best-matching resume per job automatically.

```bash
cp ~/Documents/resume.pdf resumes/
```

To rebuild the resume cache after adding new files:
```bash
python pipeline.py draft --refresh-resumes
```

---

## Email Templates

All prompts are plain text in `src/prompts/` — edit freely to match your voice:

```
src/prompts/
├── initial_email.txt       # Cold outreach template
├── followup_1.txt          # Day 4 — gentle nudge
├── followup_2.txt          # Day 8 — new hook
└── followup_3.txt          # Day 14 — graceful close
```

---

## Logging

```
logs/
├── pipeline.log    # discover / draft / send activity
└── outreach.log    # email send + follow-up history
```

---

## Troubleshooting

**`No search JSON files found`** — Run `/job-search` in Claude Code first. Results are saved to `data/searches/` automatically.

**`No resumes found`** — Ensure PDFs are directly in `resumes/` (no subdirectories).

**`Failed to scrape JD`** — The page may require JavaScript. Paste the job description text directly into the Notion `Job Description Text` cell instead.

**Gmail auth errors** — Make sure you're using an App Password, not your regular account password. Requires 2FA to be enabled.

---

## Contributing

1. Fork the repo and create a feature branch
2. Make your changes and add tests if applicable
3. Open a pull request with a clear description

---

## License

MIT © Rukaiya Khan
