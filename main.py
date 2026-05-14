def main():
    print("""
Career Outreach Engine - Job Mailer

Usage:
  python src/draft_emails.py          # Draft emails from Pending rows
    --refresh-resumes                  # Rebuild resume cache
    --reprocess                        # Overwrite existing drafts
    --dry-run                          # Preview without writing to Notion

  python src/send_emails.py            # Send emails and manage follow-ups
    --status                           # Print pipeline summary
    --dry-run                          # Preview without sending

Setup:
  1. Copy .env.example to .env and fill in your credentials
  2. Add PDF resumes to the resumes/ directory
  3. Create a Notion database and set NOTION_DATABASE_ID in .env

For details, see the PRD at:
https://www.notion.so/PRD-35feb9c5f5918094a778eb874591ea33
    """)


if __name__ == "__main__":
    main()
