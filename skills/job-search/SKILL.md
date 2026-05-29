---
name: job-search
description: Search LinkedIn, Hacker News, and Twitter/X for jobs with connections, hiring manager insights, and preference-based scoring. Use when the user wants to find jobs, search for positions, or explore job opportunities.
allowed-tools: Read, Write, Bash, WebSearch, WebFetch, mcp__claude-in-chrome__*, mcp__plugin_playwright_playwright__*
---

# Multi-Source Job Search

A Claude Code skill for searching jobs across LinkedIn, Hacker News Who's Hiring, and Twitter/X. Scores and ranks results against your saved preferences, highlights network advantages, and saves structured output.

---

## Phase 1: Load Preferences & Parse Overrides

### Step 1: Load Profile

Read `/Users/rukaiyakhan/Documents/Project/career-outreach-engine/claude-job-profile.json`. Check for the `preferences` key.

**If no preferences found**, say:

> No search preferences found. Run `/job-preferences` first to set your target titles, salary range, and filters.

Then **STOP**. Do not prompt the user to set preferences inline.

**If preferences exist**, load them:

```json
{
  "targetTitles": ["Staff AI Engineer", "Principal ML Engineer"],
  "minBaseSalary": "$250K",
  "remotePreference": "remote only",
  "excludePatterns": ["junior", "associate", "intern", "entry level"],
  "defaultTimeRange": "last week"
}
```

### Step 2: Parse User Overrides

The user may pass overrides when invoking the skill:

- **Time range**: `last week`, `2 weeks`, `month` — overrides `defaultTimeRange`
- **Source filter**: `linkedin`, `hn`, `twitter`, or any combination — limits which sources to query (default: all three)
- **Keywords**: any additional keywords to use alongside `targetTitles`

Display the active search config before proceeding:

> **Search config:**
> - Titles: Staff AI Engineer, Principal ML Engineer
> - Salary floor: $250K
> - Remote: Remote only
> - Exclude: junior, associate, intern, entry level
> - Time range: last week
> - Sources: LinkedIn, HN, Twitter

---

## Phase 2a: LinkedIn Search (Chrome MCP)

### Navigation

1. Get browser context using `tabs_context_mcp`
2. Create a new tab using `tabs_create_mcp`
3. Navigate to `https://www.linkedin.com/jobs/`
4. Verify user is logged in — use `read_page` to check for profile menu. If not logged in, say: "Please log into LinkedIn in this browser tab, then let me know when you're ready." and **wait**.

### Build Search URL

Base URL: `https://www.linkedin.com/jobs/search/`

| Parameter | Purpose | Values |
|-----------|---------|--------|
| `keywords` | Search terms | URL-encoded — `keywordModifiers` + each title from `targetTitles`, e.g. `"fall 2026 internship software engineer"` |
| `location` | Geographic area | From profile location |
| `f_WT` | Work type | `1` (on-site), `2` (hybrid), `3` (remote) |
| `f_TPR` | Time posted | `r604800` (week), `r1209600` (2 weeks), `r2592000` (month) |
| `f_E` | Experience level | `1` (internship) |
| `f_JT` | Job type | `F` (full-time), `P` (part-time), `I` (internship), `C` (contract), `T` (temporary), `V` (volunteer), `O` (other) |
| `f_JIYN` | In your network | `true` |
| `sortBy` | Sort order | `DD` (date) |

Map `employmentType`:
- "internship" → `f_JT=I`
- "full-time" → `f_JT=F`
- "part-time" → `f_JT=P`
- "contract" → `f_JT=C`
- omit if not set

Map `remotePreference`:
- "remote only" → `f_WT=3`
- "remote preferred" → `f_WT=2,3`
- "open to hybrid" → `f_WT=2,3`
- "open to all" → omit `f_WT`

Map time range:
- "last 24 hours" → `f_TPR=r86400`
- "last week" → `f_TPR=r604800`
- "2 weeks" → `f_TPR=r1209600`
- "month" → `f_TPR=r2592000`

### Extract Job Listings (max 25)

For each job card:

1. Use `read_page` to read job cards from results list
2. Click into job detail page using `computer` with left_click
3. Wait 2-3 seconds for detail page to load
4. Extract: title, company, location, posted date, applicant count, work type, apply method
5. **Skip listings where applicant count exceeds `maxApplicants` (default: 100)** — check the applicant count shown on the job detail page (e.g. "87 applicants"); if it exceeds the limit, discard the result and move on
6. **Skip citizenship-restricted listings** — scan the JD text for any of these phrases and discard the result if found:
   - "must be a US citizen", "US citizens only", "U.S. citizen required", "requires US citizenship"
   - "security clearance required", "active clearance", "secret clearance", "top secret", "TS/SCI"
   - "authorized to work in the US without sponsorship" (only skip if combined with "citizens" or "permanent residents only")
   - "no sponsorship", "no visa sponsorship", "will not sponsor"
   - Any variation of the above (case-insensitive)
7. Look for connection indicators — use `find` with query "connections work here" or "connections at"
6. Look for hiring team — use `find` with query "Meet the hiring team" or "hiring manager"
7. If hiring manager found, extract name, title, profile URL
8. Store result, navigate back to results list
9. **2-3 second delay** between each job

### Scrolling for More Results

LinkedIn uses infinite scroll:
1. Use `computer` with action "scroll", scroll_direction "down"
2. Wait 2-3 seconds for new results
3. Use `read_page` to see newly loaded cards
4. Repeat until desired count or no more results

---

## Phase 2b: Hacker News Who's Hiring (Bash + WebSearch)

### Find Current Thread

1. Use `WebSearch` to search for: `"Ask HN: Who is hiring?" site:news.ycombinator.com {current_month} {current_year}`
2. Extract the thread ID from the HN URL in the search results (e.g., `https://news.ycombinator.com/item?id=XXXXXXXX` → `XXXXXXXX`)

If no thread found for the current month, try the previous month. If still nothing, skip HN and report it.

### Fetch Comments via Firebase API

3. Fetch the thread: `curl -s "https://hacker-news.firebaseio.com/v0/item/{THREAD_ID}.json"`
4. Parse the `kids` array — these are top-level comment IDs (job postings)
5. Fetch each comment (up to 50): `curl -s "https://hacker-news.firebaseio.com/v0/item/{COMMENT_ID}.json"`
6. **0.5 second delay** between API calls

### Parse Comments

HN Who's Hiring comments typically follow this format in the `text` field:

```
Company Name | Role Title | Location | Remote | Salary Range
Description text...
Apply: URL
```

For each comment:
- Extract company, title, location, remote status, salary from the first line (pipe-delimited)
- Extract application URL if present (look for "apply" or "http" links)
- Parse salary range if present (look for patterns like `$XXXk-$XXXk`, `$XXX,XXX`)
- Extract the full text as description

### Filter Against Preferences

Skip comments that:
- Don't match any `targetTitles` (fuzzy match — "AI Engineer" matches "Staff AI Engineer")
- Match any `excludePatterns`
- Don't meet `remotePreference` (if "remote only", skip non-remote postings)
- Fall below `minBaseSalary` (if salary is listed)
- Contain citizenship-restriction phrases: "US citizens only", "no sponsorship", "no visa sponsorship", "will not sponsor", "security clearance required", "TS/SCI", "US citizen required" (case-insensitive)

---

## Phase 2c: Twitter/X Search (Chrome MCP)

### Navigation

1. Use existing browser context (or create new tab)
2. Navigate to `https://x.com/search`
3. Verify logged in — use `read_page` to check for profile avatar or compose button. If not logged in, **skip Twitter entirely** and continue with other sources. Report: "Skipped Twitter — not logged in."

### Build Search Query

Construct a Twitter advanced search query:

```
("fall 2026" OR "summer 2026") ("intern" OR "internship") ("{title1}" OR "{title2}" OR "software engineer" OR "frontend" OR "AI engineer") since:YYYY-MM-DD -is:reply
```

Map time range to `since:` date:
- "last week" → 7 days ago
- "2 weeks" → 14 days ago
- "month" → 30 days ago

### Execute Search

4. Navigate to the search URL with the query
5. Wait for results to load (3 seconds)
6. Switch to "Latest" tab if available
7. Extract tweet content, author handle, engagement (likes/retweets), and any URLs (max 20 tweets)
8. **2-3 second delays** between interactions

### Filter Against Preferences

Apply the same filtering as HN — title match, exclude patterns, remote, salary, and citizenship-restriction phrases if mentioned.

### Graceful Failure

If Twitter is inaccessible, rate-limited, or not logged in — skip entirely and continue. Report which sources succeeded and failed at the end.

---

## Phase 3: LinkedIn Detail Extraction

For LinkedIn results that passed initial filtering, extract additional network signals:

1. Connection count and names (1st-degree, 2nd-degree, alumni)
2. Hiring manager name, title, profile URL
3. Easy Apply availability
4. Applicant count and posting age
5. **JD text** — extract the full job description text for skill matching in Phase 4

This data feeds into the scoring in Phase 4.

---

## Phase 3b: JD Skill Matching

After extracting the JD text for each result (all sources), compare it against the flat skill list from `preferences.skills` in the profile.

**Flatten all skills into one list** before matching:
```
languages + frontend + databases + ai + backend + cloud + other
```

**Matching rules:**
- Case-insensitive substring match (e.g. "react" matches "React.js", "React Hooks")
- Aliases: "rag" matches "retrieval-augmented-generation", "node" matches "node.js", "postgres" matches "postgresql"
- Score = `matched_skills / total_skills_mentioned_in_JD` (capped at 1.0)

**Categorize the match:**
- **Strong match** (≥70% of JD skills matched): flag with ✅
- **Partial match** (40–69%): flag with ⚡
- **Weak match** (<40%): flag with ⚠️

**Also extract:**
- `matchedSkills[]` — skills from your profile found in the JD
- `missingSkills[]` — skills mentioned in JD not found in your profile (useful to know)

---

## Phase 4: Cross-Source Scoring

Score every result on a 0-100 normalized scale.

### Scoring Rubric

| Category | Points | Applies to |
|----------|--------|-----------|
| **JD skill match — strong (≥70%)** | **25** | **All sources** |
| **JD skill match — partial (40–69%)** | **15** | **All sources** |
| **JD skill match — weak (<40%)** | **5** | **All sources** |
| Title match (exact vs partial) | 0-20 | All sources |
| Salary meets/exceeds floor | 0-10 | All sources |
| Remote preference match | 0-10 | All sources |
| Recency (newer = higher) | 0-5 | All sources |
| Low competition (<100 applicants) | 0-5 | All sources |
| Hiring manager listed | 20 | LinkedIn only |
| 1st-degree connections | 15 | LinkedIn only |
| 2nd-degree or alumni connections | 10 | LinkedIn only |
| Easy Apply available | 5 | LinkedIn only |
| Salary explicitly listed | 10 | HN only |
| Application URL provided | 10 | HN only |
| High engagement (50+ likes) | 10 | Twitter only |

### Normalization

Max possible per source: LinkedIn 125, HN 105, Twitter 95.

Normalize all scores to 0-100:
- LinkedIn score: `raw_score * (100 / 125)`
- HN score: `raw_score * (100 / 105)`
- Twitter score: `raw_score * (100 / 95)`

Round to nearest integer. Sort all results by normalized score descending.

---

## Phase 5: Output

### 1. Terminal Display

```
============================================================
  Multi-Source Job Search Results
============================================================
  Titles: Staff AI Engineer, Principal ML Engineer
  Filters: Remote only | Last week | Salary >= $250K
  Sources: LinkedIn (12), HN (8), Twitter (5)
  Total: 25 results | Showing top 25 by score
============================================================

Score | Match | Source   | Title                        | Company       | Salary   | Location        | Signals
----- | ----- | -------- | ---------------------------- | ------------- | -------- | --------------- | --------------------------
  92  |  ✅   | LinkedIn | Staff AI Engineer            | Acme Corp     | $280K    | Remote          | Hiring mgr, 2 connections
  87  |  ✅   | LinkedIn | Principal ML Engineer        | TechStart     | $300K    | SF (Remote OK)  | 5 connections, Easy Apply
  81  |  ⚡   | HN       | AI Engineer (Staff)          | CoolStartup   | $250-300K| Remote          | Salary listed, Apply URL
  76  |  ⚠️   | Twitter  | Head of AI                   | DataCo        | —        | Remote          | 120 likes
  ...

============================================================
  Summary
  - 4 with hiring managers | 8 with connections
  - 3 sources queried | 0 failed
  - Saved to: /Users/rukaiyakhan/Documents/Project/career-outreach-engine/data/searches/search-2026-02-28T14-30-00.md
============================================================
```

### 2. Markdown File

Save full details to `/Users/rukaiyakhan/Documents/Project/career-outreach-engine/data/searches/search-{timestamp}.md`.

Create the directory if it doesn't exist.

```markdown
# Job Search Results — 2026-02-28

## Search Parameters
- Titles: Staff AI Engineer, Principal ML Engineer
- Salary floor: $250K
- Remote: Remote only
- Time range: Last week
- Sources: LinkedIn, HN, Twitter

## Results (ranked by score)

### 1. Staff AI Engineer — Acme Corp (Score: 92)
- **Source**: LinkedIn
- **Location**: Remote
- **Salary**: $280K
- **Posted**: 2 days ago | 45 applicants
- **Hiring Manager**: Jane Smith (Engineering Manager) — linkedin.com/in/janesmith
- **Connections**: 2 (John Doe, Sarah Lee)
- **Apply**: Easy Apply
- **Skill Match**: ✅ Strong (8/10) — React.js, TypeScript, Node.js, AWS Lambda, PostgreSQL, Docker, REST APIs, GraphQL
- **Missing Skills**: Kubernetes, Go
- **URL**: https://linkedin.com/jobs/view/123456

### 2. AI Engineer (Staff) — CoolStartup (Score: 81)
- **Source**: Hacker News
- **Location**: Remote
- **Salary**: $250-300K
- **Description**: Building next-gen AI infrastructure...
- **Apply**: https://coolstartup.com/careers/ai-engineer

...
```

### 3. JSON File (for pipeline integration)

After saving the markdown, also save a structured JSON to `/Users/rukaiyakhan/Documents/Project/career-outreach-engine/data/searches/search-{timestamp}.json`:

```json
{
  "searchDate": "{YYYY-MM-DD}",
  "parameters": {
    "titles": [...],
    "remotePreference": "...",
    "timeRange": "...",
    "sources": [...]
  },
  "results": [
    {
      "title": "Staff AI Engineer",
      "company": "Acme Corp",
      "url": "https://linkedin.com/jobs/view/123456",
      "source": "LinkedIn",
      "score": 92,
      "skillMatch": "Strong",
      "matchedSkills": ["React.js", "TypeScript", "Node.js"],
      "missingSkills": ["Kubernetes", "Go"],
      "location": "Remote",
      "salary": "$280K",
      "applyMethod": "Easy Apply",
      "applicantCount": 45,
      "postedDate": "2 days ago",
      "hiringManager": {"name": "Jane Smith", "title": "Engineering Manager", "profileUrl": "..."},
      "connections": [{"name": "John Doe", "degree": 1}]
    }
  ]
}
```

Use the **same timestamp** for both the `.md` and `.json` files.

### 4. Push to Notion

After saving both files, run the pipeline's discover command to push the results into Notion automatically:

```bash
cd /Users/rukaiyakhan/Documents/Project/career-outreach-engine && \
  uv run python pipeline.py discover --from-search data/searches/search-{timestamp}.json
```

If the command fails (venv not set up, missing deps), report the error but do not block — the user can run it manually later.

### 5. Queue Append (Optional, User Confirms)

If any results scored 70+, ask the user:

> **{N} jobs scored 70+** and have been pushed to your Notion pipeline as "Discovered". Would you also like me to append them to the local `application_queue.md`?

If confirmed, append to `/Users/rukaiyakhan/Documents/Project/career-outreach-engine/data/application_queue.md` under a new "## Tier 3 — Auto-Discovered" section:

```markdown
## Tier 3 — Auto-Discovered

| Score | Source | Role | Company | URL | Status |
|-------|--------|------|---------|-----|--------|
| 92 | LinkedIn | Staff AI Engineer | Acme Corp | [link](https://...) | New |
| 81 | HN | AI Engineer (Staff) | CoolStartup | [link](https://...) | New |
```

**Never modify application_queue.md without explicit user confirmation.**

---

## Safety Rules

1. **Never enter credentials** — if login is required, stop and instruct user to log in manually
2. **Never click Apply** — this skill is for searching only, not applying
3. **Never create accounts** — stop and inform user if account creation is required
4. **Respect rate limits per source**:
   - LinkedIn: 2-3 second delays between page loads
   - HN Firebase API: 0.5 second delays between requests
   - Twitter: 2-3 second delays between interactions
5. **Max results per source**: LinkedIn 25, HN 50 comments, Twitter 20 tweets
6. **Graceful degradation** — if any source fails, skip it and continue with the others. Report which sources succeeded and which failed at the end.
7. **Never modify application_queue.md without user confirmation**
8. **HN Firebase API only** — never scrape the Hacker News website directly. Always use `https://hacker-news.firebaseio.com/v0/` endpoints.
9. **Handle errors gracefully** — if a job page fails to load, skip and continue

---

## Example Invocations

**Standard search (all sources):**
```
User: /job-search
Claude: [Loads preferences, searches LinkedIn + HN + Twitter, displays ranked results]
```

**With time range override:**
```
User: /job-search 2 weeks
Claude: [Uses 2-week time range instead of default]
```

**Single source:**
```
User: /job-search hn
Claude: [Searches only Hacker News Who's Hiring]
```

**Multiple source filter:**
```
User: /job-search linkedin hn
Claude: [Searches LinkedIn and HN, skips Twitter]
```

**With extra keywords:**
```
User: /job-search agentic systems
Claude: [Adds "agentic systems" to title-based keywords]
```
