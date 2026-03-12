# Seedlist.com — Design Spec

## Context

Founders raising money waste enormous time researching investors — piecing together who's actively investing, what they actually fund (vs. what they claim), and whether they'd be a good fit. Seedlist.com solves this by building a comprehensive, LLM-researched directory of active startup investors with enough depth to power intelligent matching.

The key insight: don't trust what investors say about their thesis — infer it from their actual portfolio and behavior. Combine that with comprehensively cited first-person statements from both investors and their portfolio founders to give the fullest possible picture.

## Architecture

**Three subsystems, built sequentially:**

1. **Static Directory** — Markdown files in git → Python build script → HTML on GitHub Pages
2. **Research Agent** — Claude Code agent that researches investors, writes profiles, discovers new investors
3. **CRM Annotation Service** — Claude Code agent triggered via Google Form/Drive that enriches founder investor lists

**No dynamic hosting.** Everything public is static HTML on GitHub Pages. All "dynamic" work happens via Claude Code agents running in the background.

**Git is the database.** All investor data lives as markdown files with YAML frontmatter, checked into the repo. Every change is a commit with full history.

```
seedlist/
├── data/
│   ├── firms/              # Firm profile markdown files
│   │   └── {slug}.md
│   ├── investors/          # Individual investor markdown files
│   │   └── {slug}.md
│   └── queue.yaml          # Research queue
├── build.py                # Static site generator
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS, images, assets
├── _site/                  # Generated HTML (GitHub Pages serves this)
├── scripts/                # Utility scripts
├── CLAUDE.md               # Instructions for the research agent
└── .github/
    └── workflows/
        └── build.yml       # GitHub Action: rebuild site on push
```

## Data Model

### Firm Profile (`data/firms/{slug}.md`)

```yaml
---
name: "Acme Ventures"
slug: acme-ventures
type: firm
website: "https://acmevc.com"
location: "San Francisco, CA"
founded: 2018
fund_size: "$50M"
stage_focus: [pre-seed, seed]
sector_focus: [fintech, developer-tools]
team:
  - slug: jane-smith
    role: Partner
  - slug: bob-jones
    role: Principal
status: published  # draft | published | flagged
last_researched: 2026-03-10
---

## About

[LLM-generated summary of the firm, sourced and cited]

## Stated Thesis

[What the firm says publicly about what they invest in — clearly labeled as self-reported] [^1]

## Inferred Thesis

[LLM analysis of actual portfolio patterns: stage distribution, sector concentration,
geography, founder profiles, check sizes, co-investor patterns. This is the PRIMARY
signal used for matching.]

Based on N verified investments:
- Stage: X% pre-seed, Y% seed
- Sectors: primarily A, B, C
- Geography: ...
- Typical check size: ...
- Co-investor patterns: frequently invests alongside ...

## Portfolio

| Company | Year | Stage | Status | Source |
|---------|------|-------|--------|--------|
| WidgetCo | 2024 | Seed | Active | [^2] |

## In Their Own Words

> "Quote from firm partners or official communications" [^3]

## What Founders Say

> "Quote from portfolio founders about working with this firm" — Source [^4]

## Sources

[^1]: Source title, URL, accessed date
[^2]: ...
```

### Investor Profile (`data/investors/{slug}.md`)

```yaml
---
name: "Jane Smith"
slug: jane-smith
type: individual
firm: acme-ventures  # slug reference to firm
role: "Partner"
location: "San Francisco, CA"
stage_focus: [pre-seed, seed]
sector_focus: [fintech, developer-tools, AI]
check_size: "$250K-$1M"
social:
  twitter: "@janesmith"
  linkedin: "linkedin.com/in/janesmith"
status: published  # draft | published | flagged
last_researched: 2026-03-10
---

## Background

[Bio, career history, how they got into investing] [^1]

## Stated Thesis

[What this investor says publicly about what they look for — clearly labeled
as self-reported] [^2] [^3]

## Inferred Thesis

[LLM analysis of their actual investment behavior. This is the PRIMARY signal
for matching.]

Based on N verified investments:
- Stage: predominantly pre-seed (X%)
- Sectors: developer-tools (X%), fintech (Y%), AI (Z%)
- Founder profile: tends to back technical founders, solo founders OK
- Geography: primarily SF/NYC, some remote
- Typical check: $250K-$500K
- Speed: known for fast decisions (per founder quotes)
- Co-investors: frequently alongside [other investors]

## Portfolio

| Company | Year | Stage | Source |
|---------|------|-------|--------|
| WidgetCo | 2024 | Seed | [^4] |
| FooBar AI | 2025 | Pre-seed | [^5] |

## In Their Own Words

> "I always look for founders who are irrationally passionate about a boring
> problem." — Twitter, 2025-06-15 [^6]

> "We don't do board seats at pre-seed. Founders need space to figure things
> out." — Twenty Minute VC podcast, 2025-09-03 [^7]

## What Founders Say

> "Jane was the first check in and spent 3 hours helping us restructure our
> cap table before she even committed." — @founderhandle, Twitter [^8]

> "Most helpful investor on our cap table, hands down."
> — CEO of WidgetCo, Twenty Minute VC podcast [^9]

## Sources

[^1]: Source title, URL, accessed date
[^2]: ...
```

### Research Queue (`data/queue.yaml`)

```yaml
queue:
  - name: "John Doe"
    firm: "Beta Capital"
    source: "co-investor on WidgetCo with jane-smith"
    discovered_from: jane-smith  # which profile led to this discovery
    priority: normal  # high | normal | low
    status: pending  # pending | in_progress | completed | skipped
    added: 2026-03-10

  - name: "Beta Capital"
    type: firm
    source: "firm of John Doe, discovered via jane-smith"
    discovered_from: jane-smith
    priority: normal
    status: pending
    added: 2026-03-10
```

## Subsystem 1: Static Directory

### Build Script (`build.py`)

A Python script using Jinja2 that:

1. Reads all markdown files from `data/firms/` and `data/investors/`
2. Parses YAML frontmatter + markdown body
3. Filters to `status: published` only
4. Renders individual profile pages using HTML templates
5. Generates index/listing pages:
   - All investors (alphabetical, searchable)
   - All firms
   - By stage focus (pre-seed, seed, Series A, etc.)
   - By sector
   - By location
6. Generates a JSON search index for client-side search (investor name, firm, sectors, stages)
7. Outputs everything to `_site/`

**Dependencies:** `python-frontmatter`, `markdown`, `jinja2`, `pyyaml`

### Templates

- `base.html` — site shell, nav, footer
- `investor.html` — individual investor profile page
- `firm.html` — firm profile page
- `index.html` — homepage with search
- `listing.html` — filtered listing pages (by stage, sector, etc.)

### GitHub Action

On push to `main`:
1. Run `build.py`
2. Deploy `_site/` to GitHub Pages
3. Custom domain: seedlist.com

### Design

Clean, minimal, fast. Content-focused. Think Crunchbase but simpler and more opinionated. No login required for the public directory.

## Subsystem 2: Research Agent

A Claude Code agent session that operates on the repo, guided by `CLAUDE.md`.

### Core Principles (encoded in CLAUDE.md)

1. **Accuracy above all.** Every factual claim must have a cited source. If you cannot find a verifiable source, do not include the claim. A shorter, accurate profile is always better than a longer, inaccurate one.

2. **Comprehensive citations.** Use footnote-style citations (`[^N]`). Every source must include: title, URL, and access date. Re-verify all existing citations when updating a profile.

3. **Infer thesis from behavior, not self-description.** The "Inferred Thesis" section is the most important part of each profile. Build it by analyzing actual portfolio investments, not stated preferences. The "Stated Thesis" section is secondary and must be clearly labeled as self-reported.

4. **Hunt for first-person statements.** Actively search for direct quotes from the investor (Twitter/X, blog posts, podcasts, conference talks, newsletters, interviews) AND from portfolio founders about their experience. Include as many relevant quotes as possible with full attribution.

5. **Discovery-driven growth.** When researching an investor, extract co-investors and portfolio companies. Add newly discovered investors/firms to `queue.yaml`.

6. **Source quality hierarchy.** Prefer: firm website > SEC filings/regulatory > major press > LinkedIn > social media > secondary aggregators. Note the source tier in citations.

### Agent Workflow

```
1. Read queue.yaml, pick next pending item
2. Set status to in_progress
3. Web search for the investor/firm
4. For each source found:
   a. Read and extract relevant facts
   b. Record source URL, title, date
   c. Look for first-person quotes (investor + founders)
5. Build/update the markdown profile:
   a. Structured frontmatter
   b. Background section (cited)
   c. Stated thesis (cited, labeled as self-reported)
   d. Portfolio table (each entry cited)
   e. Inferred thesis (analyzed from portfolio data)
   f. "In Their Own Words" section (all found quotes, cited)
   g. "What Founders Say" section (all found quotes, cited)
   h. Sources section with all footnotes
6. Extract new leads:
   a. Co-investors → add to queue
   b. Portfolio companies → note for cross-referencing
   c. Mentioned firms/investors → add to queue
7. Commit the profile
8. Mark queue item as completed
9. Repeat
```

### Two-Pass Review

After the research agent writes a profile (first pass), a second Claude Code agent pass reviews it:

1. Re-reads every citation source URL
2. Verifies each claim matches its cited source
3. Checks for unsourced claims and flags or removes them
4. Validates the inferred thesis against the portfolio data
5. Checks quote accuracy against sources
6. If issues found → flags profile as `status: flagged` with notes
7. If clean → sets `status: published`

Profiles that fail review stay as drafts and get a `review_notes` field in frontmatter explaining what needs fixing.

## Subsystem 3: CRM Annotation Service

### Intake

- Google Form at seedlist.com/annotate (static page linking to Google Form)
- Founder uploads CSV with their investor list (columns: investor name, firm, any other fields they have)
- Provides their email for delivery

### Processing (Claude Code Agent)

1. Agent watches Google Drive folder for new submissions
2. Reads the uploaded CSV
3. For each row:
   a. Fuzzy-match investor name + firm against `data/investors/` and `data/firms/`
   b. If match found: annotate with our data (inferred thesis, stage focus, sectors, check size, portfolio highlights)
   c. If no match: flag as "not in our database" and optionally add to research queue
4. Similarity matching:
   a. Build a profile of the founder's existing investor list (what stages, sectors, check sizes are represented)
   b. Find investors in our database with similar inferred theses that are NOT on their list
   c. Rank by similarity and add as recommendations
5. Generate enriched CSV with:
   - Original columns preserved
   - Added columns: seedlist_match (yes/no), inferred_thesis, stage_focus, sector_focus, check_size, seedlist_url
   - Additional rows at the bottom: recommended similar investors
6. Email the enriched CSV back to the founder

### Matching Approach

Similarity matching uses the LLM directly — no embeddings infrastructure needed:
- Summarize the founder's existing investor list as a "pattern" (what types of investors they're targeting)
- For each candidate investor in our database, ask the LLM: "How similar is this investor's inferred thesis to the founder's target pattern?"
- Rank by LLM-assessed similarity
- Return top N recommendations with explanations of why each was recommended

## Build Sequence

### Phase 1: Foundation (Subsystem 1)
1. Initialize git repo, set up project structure
2. Create sample investor and firm markdown files (hand-written, to establish the format)
3. Build `build.py` static site generator
4. Create Jinja2 templates
5. Set up GitHub Action for auto-deploy
6. Configure GitHub Pages + custom domain (seedlist.com)
7. Verify: site builds and deploys with sample profiles

### Phase 2: Research Agent (Subsystem 2)
1. Write `CLAUDE.md` with research agent instructions
2. Create initial `queue.yaml` with a few seed investors
3. Test the agent: run Claude Code, let it research one investor end-to-end
4. Iterate on CLAUDE.md based on output quality
5. Implement the two-pass review workflow
6. Run the agent on a batch, review results, refine
7. Verify: agent produces accurate, well-cited profiles that auto-publish

### Phase 3: CRM Service (Subsystem 3)
1. Set up Google Form + Drive integration
2. Write the CRM annotation agent instructions
3. Build the matching logic
4. Test with sample CSVs
5. Verify: end-to-end flow from form submission to enriched CSV delivery

## Verification

### Subsystem 1
- `python build.py` runs without errors
- Generated HTML renders correctly in browser
- All internal links work
- Search index includes all published profiles
- GitHub Action deploys successfully
- seedlist.com loads and shows profiles

### Subsystem 2
- Agent picks up queue items and researches them
- Every claim in generated profiles has a footnote citation
- Citation URLs are valid and support the claims they back
- Inferred thesis is grounded in actual portfolio data, not self-reported claims
- First-person quotes are accurate and attributed
- New investors/firms are discovered and added to queue
- Two-pass review catches and flags issues
- Only reviewed profiles get published

### Subsystem 3
- CSV upload via Google Form works
- Fuzzy matching correctly identifies investors in our database
- Annotations include accurate data from our profiles
- Similar investor recommendations are relevant
- Enriched CSV is delivered to founder's email
