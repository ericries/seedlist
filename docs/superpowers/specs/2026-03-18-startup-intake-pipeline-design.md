# Startup Intake & Enrichment Pipeline

**Date:** 2026-03-18
**Status:** Approved

## Problem

Eric helps startups raise money. Currently this is manual: founders send investor lists, Eric runs them through Seedlist enrichment, adds his own recommendations. There's no structured intake, no automated enrichment delivery, and no systematic way to evaluate whether a startup is ready to fundraise or worth Eric's personal network capital.

## Solution

A Google Form intake → Google Sheets storage → Claude Code processing pipeline that:
1. Sends every founder an enriched investor list automatically
2. Sends Eric a private LLM evaluation of the startup's fundraising readiness

## Architecture

```
Google Form → Google Sheet → `sl process-intake` → two outputs:
                                  ├─→ Founder: enriched CSV via email
                                  └─→ Eric: private evaluation via email
```

No servers, no infrastructure. Google Forms/Sheets/Gmail + Claude Code + existing Seedlist enrichment.

## Google Form Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Company name | Short text | Yes | |
| One-liner | Short text | Yes | "What does your company do in one sentence?" |
| Website | URL | No | |
| Sector | Multi-select checkboxes | Yes | fintech, AI/ML, developer tools, health/bio, consumer, enterprise SaaS, infrastructure, crypto/web3, climate, marketplace, other |
| Stage | Dropdown | Yes | pre-seed, seed, Series A, Series B+ |
| Raising amount | Short text | Yes | e.g. "$2M" |
| Target valuation | Short text | No | e.g. "$10M pre-money" |
| Traction | Long text | Yes | "Revenue, users, growth rate, key metrics" |
| Team | Long text | Yes | "Founder names, backgrounds, prior exits, team size" |
| Deck | File upload | No | PDF or Google Slides link |
| Deck URL | URL | No | Alternative to file upload (DocSend, Google Drive, etc.) |
| Current investor list | File upload | No | CSV with investor names |
| Founder name | Short text | Yes | For email personalization |
| Founder email | Email | Yes | Where to send results |

Responses auto-populate a linked Google Sheet. The form should require Google sign-in ("Limit to 1 response" enabled) to prevent spam/bot submissions.

## Google Sheet Structure

The Sheet has two tabs:

### Tab 1: "Responses" (auto-populated by Form)
All form fields as columns, plus these manually-added columns:
- **Status**: `new` | `processing` | `sent` | `error`
- **Enriched CSV URL**: link to the generated CSV in Google Drive
- **Founder Email Body**: populated by `intake.py` before sending
- **Eric Email Body**: populated by `intake.py` before sending
- **Email Trigger**: set to `send` to trigger Apps Script
- **Notes**: for error messages or manual notes

### Tab 2: "Config"
Key-value pairs in columns A and B. Lookup by key name (column A), not row number:

| Key | Value |
|-----|-------|
| `eric_email` | Eric's email address |
| `from_name` | Seedlist |
| `founder_email_subject` | Your enriched investor list from Seedlist |
| `eric_email_subject` | Intake evaluation: {company_name} |
| `apps_script_api_key` | (shared secret for web app auth) |

## Scheduling

Eric runs `sl process-intake` manually when he wants to process new submissions. This matches the "no infrastructure" goal. If automation is desired later, a GitHub Action on a cron schedule could run the script, but that requires storing Google/Anthropic credentials as GitHub secrets.

A daily processing cap of 20 rows per run prevents runaway API spend if the form is discovered by bots.

## `sl process-intake` Command

New subcommand in `scripts/sl` that delegates to `scripts/intake.py`.

### Flow

```
1. Authenticate with Google Sheets API (service account)
2. Read rows where Status = "new" (max 20 per run)
3. For each row:
   a. Set Status = "processing"
   b. Download CSV attachment (if any) from Google Drive
   c. Run enrichment (reuse existing enrichment logic)
   d. Generate investor recommendations based on sector/stage
   e. Upload enriched CSV to Google Drive
   f. Compose founder email body, write to Sheet
   g. Generate private LLM evaluation via Anthropic API
   h. Write evaluation to Eric Email Body column
   i. Call Apps Script web app to send both emails
   j. Set Status = "sent"
   k. On error: set Status = "error", write error to Notes column
4. Log summary to ~/.config/seedlist/intake.log
```

### Enrichment

Reuses the core matching logic from `cmd_enrich` in `scripts/sl`. The existing command already does:
- Match investor names against published profiles
- Fuzzy matching with confidence scores
- Add Seedlist metadata (stage focus, sector focus, check size, thesis summary)
- Generate similarity-based recommendations

For intake, we additionally:
- Filter recommendations to match the startup's declared sector and stage
- Sort recommendations by relevance to this specific startup
- Add a "Why this investor?" column using templates (not LLM — fast and free):
  - "Invests in {stage} {sector}; check size {check_size}"
  - "Active in {sector}; last investment {date} ({company})"
  - "Stage match: focuses on {stage}; sectors include {overlapping_sectors}"

### Private Evaluation (for Eric)

`intake.py` calls the Anthropic API directly using the key at `ANTHROPIC_API_KEY` env var (or `~/.config/seedlist/anthropic_key`). Uses `claude-sonnet-4-6` for cost efficiency.

**The form data is the input to the LLM here — this is intentional and acceptable because it's Eric's private evaluation, not data that flows into the public directory or research queue.**

On API failure: retry once after 5 seconds. If still failing, mark row as `error` with message "LLM evaluation failed" and continue to next row. The founder still gets their enriched CSV (enrichment doesn't require the LLM).

#### Evaluation Structure

```markdown
# Intake Evaluation: {Company Name}

**Submitted:** {date}
**Stage:** {stage} | **Raising:** {amount} | **Sector:** {sector}

## One-liner
{their one-liner}

## Team Assessment
- Founder backgrounds and relevant experience
- Technical depth
- Gaps or concerns
- Prior startup/exit history

## Market
- What can be inferred from sector and one-liner
- (Note: limited assessment if no market data provided in form)

## Traction
- Current metrics relative to stage benchmarks
- Growth trajectory
- Key risks

## Fundraising Readiness

**READY TO FUNDRAISE AT {STAGE}** or **NOT YET READY**

### If ready:
- Strengths to highlight in pitch
- Likely investor objections and how to address them
- Recommended investor types (angel vs institutional, generalist vs specialist)

### If not ready:
- What needs to happen before fundraising
- Specific feedback for the team (shareable if Eric chooses)
- Suggested timeline

## Network Recommendation
- Whether to make personal intros from your network
- If yes: which specific investors from Seedlist would be best fits and why
- If no: why not, and what would change your mind
```

If no deck is provided, the evaluation notes: "No deck provided — assessment based on form answers only."

### Email Delivery

Uses Apps Script deployed as a web app. Claude Code calls it via HTTP POST.

#### Apps Script

```javascript
function doPost(e) {
  var params = JSON.parse(e.postData.contents);

  // Authenticate with shared secret
  var expectedKey = PropertiesService.getScriptProperties().getProperty('API_KEY');
  if (params.api_key !== expectedKey) {
    return ContentService.createTextOutput("unauthorized").setMimeType(ContentService.MimeType.TEXT);
  }

  if (params.action === "send_founder") {
    GmailApp.sendEmail(params.to, params.subject, "", {
      htmlBody: params.body,
      name: params.from_name || "Seedlist"
    });
  }

  if (params.action === "send_eric") {
    GmailApp.sendEmail(params.to, params.subject, "", {
      htmlBody: params.body,
      name: "Seedlist Intake"
    });
  }

  return ContentService.createTextOutput("ok");
}
```

`intake.py` calls this endpoint with the API key from `~/.config/seedlist/config.yaml`.

#### Founder Email Template

```
Subject: Your enriched investor list from Seedlist

Hi {founder_name},

Thanks for submitting {company_name} to Seedlist.

{if CSV was provided:}
We've enriched your investor list with Seedlist intelligence — stage focus,
sector focus, check sizes, and inferred thesis summaries for each matched
investor. We also added recommendations for similar investors you may not
have considered.

Download your enriched list: {enriched_csv_url}

{if no CSV:}
You didn't include an investor list, so we weren't able to enrich it.
Reply to this email with a CSV of investor names and we'll send you
an enriched version.

{always:}
Best,
Seedlist
```

## File Structure

```
scripts/
  sl                      # Add process-intake command routing
  intake.py               # Main intake processing logic
docs/
  intake-setup.md         # One-time setup instructions (Form, Sheet, credentials)
```

## Credentials & Security

- **Google service account key**: stored at `~/.config/seedlist/credentials.json`
  - Has read/write access to the specific Google Sheet
  - Has access to Google Drive for file uploads/downloads
  - NEVER committed to the repo
- **Anthropic API key**: `ANTHROPIC_API_KEY` env var or `~/.config/seedlist/anthropic_key`
- **Apps Script web app URL + API key**: stored in `~/.config/seedlist/config.yaml`
  - Web app deployed with "execute as me" permissions
  - API key validated on every request (stored in Apps Script Properties)
- **Form file upload folder**: shared with the service account email so it can download decks and CSVs
- **Founder form data**: processed by LLM for evaluation but never written to queue.yaml, profile files, or any public-facing part of Seedlist
- **Private evaluations**: emailed to Eric only, not stored in the repo
- **Defense-in-depth**: `credentials.json`, `config.yaml`, `*.key`, and `anthropic_key` added to `.gitignore`

## Google API Setup (One-Time)

1. Create Google Cloud project (or reuse existing)
2. Enable Google Sheets API and Google Drive API
3. Create service account, download JSON key to `~/.config/seedlist/credentials.json`
4. Share the Google Sheet with the service account email
5. Share the Form's file upload destination folder with the service account email
6. Create Apps Script in the Google Sheet, add the `doPost` function
7. Set the API key in Script Properties: `PropertiesService.getScriptProperties().setProperty('API_KEY', 'your-secret-key')`
8. Deploy Apps Script as web app ("execute as me", "anyone with the link")
9. Store the web app URL and API key in `~/.config/seedlist/config.yaml`:
   ```yaml
   apps_script_url: "https://script.google.com/macros/s/.../exec"
   apps_script_api_key: "your-secret-key"
   google_sheet_id: "1abc..."
   ```

## Dependencies

- `google-api-python-client` — Sheets/Drive API
- `google-auth` — Service account authentication
- `anthropic` — Claude API for evaluations
- `python-frontmatter`, `pyyaml` — Existing deps
- No new infrastructure, no servers, no databases

## Edge Cases

- **No CSV uploaded**: Skip enrichment, still send evaluation to Eric. Founder email says "Upload an investor list next time for enriched results."
- **CSV with no matches**: Send CSV back with Seedlist recommendations only (no enrichment columns populated).
- **No deck**: Evaluation notes "No deck provided — assessment based on form answers only." Deck is optional context, not required.
- **Duplicate submissions**: Check by normalized company name (lowercase, strip Inc/LLC/Corp) + founder email. If duplicate within 7 days, skip and note in Status column.
- **API rate limits**: Google Sheets API has 300 requests/minute — more than sufficient. Process one row at a time.
- **Large CSV**: Cap at 1000 rows. If larger, truncate and note in founder email.
- **LLM API failure**: Retry once. If still failing, send founder their enriched CSV (enrichment is pure Python, no LLM needed) and mark evaluation as failed. Eric gets notified via the error status in the sheet.
- **Daily cap**: Max 20 rows per `process-intake` run to limit API spend from spam.
- **Deck access**: File uploads go to the Form owner's Drive. The service account must have access to the upload folder (shared in setup step 5). If the deck can't be downloaded, evaluation proceeds without it.
