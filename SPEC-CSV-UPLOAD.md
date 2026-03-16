# CSV Upload & Enrichment — MVP Spec

## The Problem

Eric helps startups raise money. Founders send him their investor target list (usually a spreadsheet or CSV). He manually cross-references it against his knowledge. This doesn't scale.

## The Solution

A page on seedlist.com where Eric (and eventually founders) can upload a CSV of investor names, and get back an enriched version with Seedlist intelligence attached.

## User Flow

1. User visits `seedlist.com/enrich` (or similar)
2. Uploads a CSV file (drag-and-drop or file picker)
3. System matches each row against Seedlist's investor/firm profiles
4. User sees a preview table showing matches and enrichment
5. User downloads the enriched CSV

## Input Format

Accept messy real-world CSVs. The system should handle:

- **Minimal:** Just a column of investor names (e.g., "Ron Conway", "Sequoia Capital")
- **Typical:** Name, Firm, Email, Stage, Notes (CRM export from Affinity, HubSpot, etc.)
- **No fixed schema.** Auto-detect which columns contain investor names and firm names using fuzzy matching against the Seedlist database.

Column detection heuristic:
1. For each column, try matching values against known investor names and firm names
2. The column with the highest match rate is the "name" column
3. If a second column also matches firms, it's the "firm" column
4. Everything else passes through untouched

## Matching Logic

For each row in the uploaded CSV:

1. **Exact match** on investor name → link to profile
2. **Fuzzy match** (Levenshtein distance, case-insensitive, ignore suffixes like "Jr.", "III") → suggest with confidence score
3. **Firm match** — if the investor isn't in Seedlist but their firm is, still enrich with firm-level data
4. **No match** — flag as "not in database" so the user knows what's missing

Match against:
- `data/investors/*.md` → name, slug
- `data/firms/*.md` → name, slug
- All names in `data/queue.yaml` (pending profiles we haven't written yet — note as "coming soon")

## Enrichment Columns

For each matched investor, append these columns to the CSV:

| Column | Source | Description |
|--------|--------|-------------|
| `seedlist_match` | system | "exact", "fuzzy", "firm_only", "none" |
| `seedlist_confidence` | system | 0.0-1.0 match confidence |
| `seedlist_url` | system | Link to profile on seedlist.com |
| `seedlist_status` | frontmatter | "published", "draft", "queued" |
| `investor_stage_focus` | frontmatter | e.g., "pre-seed, seed" |
| `investor_sector_focus` | frontmatter | e.g., "fintech, developer-tools" |
| `investor_check_size` | frontmatter | e.g., "$250K-$1M" |
| `investor_location` | frontmatter | e.g., "San Francisco, CA" |
| `firm_name` | frontmatter | Firm name |
| `last_active` | frontmatter | last_verified_investment date |
| `inferred_thesis_summary` | body | First 200 chars of Inferred Thesis section |

## Architecture

### Option A: Static-site only (MVP — recommended)

Everything runs **client-side in the browser**. No backend needed.

1. At build time, `build.py` generates a `enrichment-index.json` containing all investor/firm names, slugs, frontmatter fields, and thesis summaries
2. The `/enrich` page loads this JSON and does all matching/enrichment in JavaScript
3. CSV parsing and generation happens in the browser using a library like PapaParse
4. No data leaves the user's browser — privacy-friendly

**Pros:** No backend, no hosting costs, deploys with existing GitHub Pages pipeline
**Cons:** Index file could get large (but 200 investors × ~500 bytes = ~100KB — fine); no server-side fuzzy matching

### Option B: Python CLI tool

A `scripts/sl enrich input.csv output.csv` command that Eric runs locally.

**Pros:** Full Python ecosystem for fuzzy matching, can handle large files
**Cons:** Only Eric can use it, not self-serve

### Recommendation: Build both

1. **Phase 1:** `sl enrich` CLI command (Eric can use immediately)
2. **Phase 2:** Browser-based `/enrich` page (self-serve for founders)

The enrichment logic is the same — just the I/O differs. Phase 1 validates the matching logic; Phase 2 wraps it in a web UI.

## Phase 1: `sl enrich` CLI

Add to `scripts/sl`:

```
sl enrich INPUT.csv [OUTPUT.csv]   # Enrich a CSV with Seedlist data
```

If OUTPUT is omitted, write to `INPUT_enriched.csv`.

Implementation:
1. Load all investor/firm profiles (reuse existing `frontmatter.load()` pattern)
2. Build name→profile lookup (exact + normalized)
3. For fuzzy matching, use `difflib.SequenceMatcher` (stdlib, no new dependencies)
4. Parse input CSV with `csv` module
5. Auto-detect name/firm columns
6. For each row, find best match, append enrichment columns
7. Write output CSV

## Phase 2: Browser `/enrich` Page

### Build-time: Generate enrichment index

In `build.py`, add a function to generate `_site/enrichment-index.json`:

```json
{
  "investors": [
    {
      "name": "Ron Conway",
      "slug": "ron-conway",
      "firm": "sv-angel",
      "firm_name": "SV Angel",
      "role": "Founder & Managing Partner",
      "location": "San Francisco, CA",
      "stage_focus": ["seed", "growth"],
      "sector_focus": ["consumer-internet", "enterprise-saas", "ai-ml"],
      "check_size": "$25K-$100K",
      "last_active": "~2023",
      "status": "published",
      "thesis_summary": "Based on 45 verified investments: 80% seed stage..."
    }
  ],
  "firms": [...],
  "queued": [
    {"name": "Some Investor", "type": "individual", "firm": "Some Firm"}
  ]
}
```

### Client-side: `/enrich` page

- **Upload area:** Drag-and-drop or file picker for CSV
- **Preview table:** Show first 10 rows with match status highlighted (green=exact, yellow=fuzzy, red=none)
- **Download button:** Generate and download enriched CSV
- **Tech:** Vanilla JS + PapaParse (CDN). No framework needed.
- **Fuzzy matching:** Use a simple Levenshtein implementation in JS (~30 lines)
- **Styling:** Match existing seedlist.com look

## Files to Create/Modify

| File | Action |
|------|--------|
| `scripts/sl` | Add `enrich` command |
| `build.py` | Add `enrichment-index.json` generation |
| `templates/enrich.html` | New page template |
| `static/enrich.js` | Client-side matching + CSV logic |
| `static/papaparse.min.js` | CSV parser (vendored or CDN) |

## Implementation Order

1. `sl enrich` CLI command (validates matching logic, Eric can use today)
2. Enrichment index generation in `build.py`
3. `/enrich` page with upload, preview, download

## Success Criteria

- Upload a real founder CSV (e.g., 50 investors) and get >80% match rate against Seedlist's 35+ published profiles
- Enriched CSV opens cleanly in Excel/Google Sheets
- End-to-end time < 2 seconds for 500-row CSV (both CLI and browser)
- No data sent to any server (browser version)
