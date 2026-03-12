# Seedlist Research Agent Instructions

## Project Overview

Seedlist.com is an LLM-researched directory of active startup investors. The core insight: don't trust what investors say about their thesis — infer it from their actual portfolio and behavior. Combine that with comprehensively cited first-person statements from both investors and their portfolio founders to give the fullest possible picture.

- **Data format:** Markdown files with YAML frontmatter in `data/firms/` and `data/investors/`
- **Database:** Git. Every change is a commit with full history.
- **Site generation:** `python build.py` reads markdown files, filters to `status: published`, and renders static HTML to `_site/`
- **Deployment:** GitHub Pages via GitHub Action on push to `main`
- **Research queue:** `data/queue.yaml` tracks pending, in-progress, and completed research tasks

## Research Workflow

1. **Pick work:** Read `data/queue.yaml`, select the next `status: pending` item (prefer `priority: high` items first).
2. **Claim it:** Set the item's status to `in_progress` in `queue.yaml` and commit.
3. **Research:** Web search for the investor or firm using the WebSearch and WebFetch tools. Search broadly:
   - Firm website and "About" / "Team" / "Portfolio" pages
   - Crunchbase, PitchBook, AngelList profiles
   - SEC filings and regulatory documents
   - Press coverage (TechCrunch, Forbes, Bloomberg, etc.)
   - LinkedIn profiles
   - Twitter/X posts, blog posts, podcast appearances, conference talks, newsletters
   - Founder testimonials and reviews
4. **Extract facts:** For each source, extract relevant facts, record the URL/title/access date, and look for first-person quotes from both the investor and portfolio founders.
5. **Build the profile:** Create or update the markdown file with all required sections (see Data Format below).
6. **Discover new leads:** Extract co-investors from portfolio companies, note mentioned investors and firms, and add them to `queue.yaml` with the `discovered_from` field set to the current profile's slug.
7. **Commit:** Commit the new or updated profile with a descriptive message (e.g., "Add profile: Jane Smith, Partner at Acme Ventures").
8. **Mark complete:** Set the queue item's status to `completed` in `queue.yaml` and commit.
9. **Repeat:** Move to the next pending item.

## Data Format

### Firm Profile (`data/firms/{slug}.md`)

Use `data/firms/acme-ventures.md` as the canonical example. The structure is:

```yaml
---
name: "Firm Name"
slug: firm-name
type: firm
website: "https://firmwebsite.com"
location: "City, State"
founded: 2020
fund_size: "$100M"
stage_focus: [pre-seed, seed]
sector_focus: [fintech, developer-tools, infrastructure]
team:
  - slug: partner-name
    role: Partner
  - slug: principal-name
    role: Principal
status: draft  # draft | published | flagged
last_researched: 2026-03-12
---
```

Required markdown sections, in order:

1. **## About** — Summary of the firm, its history, fund structure, and approach. Every factual claim cited.
2. **## Stated Thesis** — What the firm says publicly about what they invest in. Clearly labeled as self-reported. Cited from firm website, interviews, etc.
3. **## Inferred Thesis** — LLM analysis of actual portfolio patterns. This is the PRIMARY signal. Include:
   - Percentage breakdown by sector
   - Stage distribution
   - Geographic concentration
   - Typical check size and valuation ranges
   - Founder profile patterns (technical founders, repeat founders, etc.)
   - Co-investor patterns
   - Any patterns not mentioned in their stated thesis
4. **## Portfolio** — Table of known investments with columns: Company, Stage, Year, Sector, Status. Each entry cited.
5. **## In Their Own Words** — Direct quotes from firm partners and official communications. Full attribution with source.
6. **## What Founders Say** — Quotes from portfolio founders about their experience with the firm. Full attribution.
7. **## Sources** — All footnote references with title, URL, and access date.

### Investor Profile (`data/investors/{slug}.md`)

```yaml
---
name: "Investor Name"
slug: investor-name
type: individual
firm: firm-slug  # slug reference to the firm profile
role: "Partner"
location: "City, State"
stage_focus: [pre-seed, seed]
sector_focus: [fintech, developer-tools, AI]
check_size: "$250K-$1M"
social:
  twitter: "@handle"
  linkedin: "linkedin.com/in/handle"
status: draft  # draft | published | flagged
last_researched: 2026-03-12
---
```

Required markdown sections, in order:

1. **## Background** — Bio, career history, how they got into investing. Cited.
2. **## Stated Thesis** — What this investor says publicly about what they look for. Clearly labeled as self-reported.
3. **## Inferred Thesis** — Analysis of their actual investment behavior. This is the PRIMARY signal. Include:
   - Stage distribution (e.g., "predominantly pre-seed at X%")
   - Sector breakdown with percentages
   - Founder profile preferences (technical founders, solo founders, etc.)
   - Geographic focus
   - Typical check size
   - Decision speed (if known from founder reports)
   - Co-investor patterns
4. **## Portfolio** — Table of known investments with columns: Company, Year, Stage, Source.
5. **## In Their Own Words** — Direct quotes from the investor. Sources: Twitter/X, blog posts, podcast transcripts, conference talks, newsletters, interviews. Full attribution.
6. **## What Founders Say** — Quotes from founders about working with this investor. Full attribution.
7. **## Sources** — All footnote references.

### Research Queue (`data/queue.yaml`)

```yaml
queue:
  - name: "Investor or Firm Name"
    type: firm  # firm | individual (omit for individual)
    firm: "Firm Name"  # for individuals, the firm they belong to
    source: "description of how this lead was found"
    discovered_from: slug-of-profile  # which profile research led to this discovery
    priority: normal  # high | normal | low
    status: pending  # pending | in_progress | completed | skipped
    added: 2026-03-12
```

## Citation Requirements

**Every factual claim MUST have a footnote citation.** No exceptions.

### Format

Use markdown footnote syntax throughout the profile:

```markdown
The firm manages $85M across two funds [^1].
```

In the Sources section at the bottom:

```markdown
[^1]: Acme Ventures website, "About Us," accessed March 2026. https://acmeventures.com/about
[^2]: Crunchbase profile for Acme Ventures, accessed March 2026. https://crunchbase.com/organization/acme-ventures
```

Each source entry must include:
- **Title** of the source (article title, page name, podcast episode, etc.)
- **URL** (full URL, not shortened)
- **Access date** (month and year at minimum)

### Source Quality Hierarchy

Prefer sources in this order:

1. **Firm website** (most authoritative for self-reported information)
2. **SEC filings and regulatory documents** (most authoritative for fund size, LP data)
3. **Major press** (TechCrunch, Forbes, Bloomberg, WSJ, etc.)
4. **LinkedIn** (for career history, role verification)
5. **Social media** (Twitter/X, for quotes and real-time activity)
6. **Secondary aggregators** (Crunchbase, PitchBook, AngelList — useful but verify independently when possible)

### Accuracy Above All

A shorter, accurate profile is always better than a longer, inaccurate one. If you cannot find a verifiable source for a claim, do not include it. When sources conflict, note the discrepancy rather than picking one.

**No unsourced claims allowed.** If a section would be empty because no sourced information is available, write "No verified information available at this time" rather than speculating.

## Inferred vs Stated Thesis

These two sections serve fundamentally different purposes.

### Stated Thesis

This is what the investor says publicly about their investment focus. It comes from their website, interviews, blog posts, and public talks. Always label it clearly as self-reported:

> Acme Ventures publicly describes their focus as backing "technical founders reshaping financial infrastructure."

Cite every claim. This section tells founders what the investor *wants* to be known for.

### Inferred Thesis (PRIMARY Signal)

This is the most important section of every profile. It is your analysis of what the investor *actually does*, based on their portfolio data. It tells founders what the investor truly invests in, regardless of their marketing.

Include:
- **Sector percentages** — e.g., "48% fintech, 30% developer tools, 13% data infrastructure"
- **Stage distribution** — e.g., "70% seed, 30% pre-seed"
- **Geographic patterns** — where portfolio companies are based
- **Check sizes** — average and range at each stage
- **Valuation ranges** — median pre-money at each stage (if discoverable)
- **Founder profile patterns** — technical co-founders, prior experience at specific companies, repeat founders
- **Co-investor patterns** — which other investors frequently appear alongside them
- **Pricing model preferences** — any patterns in business model of portfolio companies
- **Notable gaps** — things they claim to invest in but don't, or invest in but don't claim

Ground every inference in data. State how many verified investments the analysis is based on. When sample size is small, say so.

## First-Person Quotes

Actively hunt for direct quotes. They make profiles dramatically more useful for founders.

### Where to Search

- **Twitter/X** — search for the investor's handle and name
- **Blog posts** — personal blog, firm blog, guest posts on other sites
- **Podcast appearances** — Twenty Minute VC, Venture Voices, etc. Search for transcripts.
- **Conference talks** — SaaStr, TechCrunch Disrupt, SeedConf, etc.
- **Newsletter posts** — Substack, email newsletters
- **Interviews** — press interviews, YouTube appearances

### What to Collect

**"In Their Own Words"** — The investor's own statements about:
- What they look for in founders
- How they make investment decisions
- Their view on markets, trends, stages
- Advice they give founders
- How they think about portfolio support

**"What Founders Say"** — Portfolio founder statements about:
- Their experience working with this investor
- What the investor did that was helpful (or not)
- How the investor behaved during fundraising
- Post-investment support quality

### Attribution

Every quote must include:
- Who said it (name and role)
- Where it was said (publication, podcast, platform)
- When (date or at least year)
- Footnote citation to the source

## Discovery

Research is self-reinforcing. Every profile you research should yield new leads.

### What to Extract

- **Co-investors:** When reviewing portfolio companies, note who else invested. Each co-investor is a potential new queue item.
- **Portfolio company mentions:** Track portfolio companies for cross-referencing across profiles.
- **Referenced investors/firms:** If an investor mentions other investors in interviews or on social media, add them to the queue.

### Adding to Queue

When adding a new lead to `queue.yaml`:

```yaml
  - name: "New Investor Name"
    firm: "Their Firm"
    source: "co-investor on WidgetCo seed round with jane-smith"
    discovered_from: jane-smith
    priority: normal
    status: pending
    added: 2026-03-12
```

Always set `discovered_from` to the slug of the profile that led to this discovery. This creates a traceable graph of how the directory grows.

For firms, also add:

```yaml
    type: firm
```

## Two-Pass Review Workflow

Every profile goes through two passes before publication.

### First Pass: Research and Writing

Follow the standard research workflow above. Set `status: draft` in the frontmatter when you create or update the profile.

### Second Pass: Verification Review

After writing a profile, perform a verification review:

1. **Re-read every cited source.** Use WebFetch to load each URL in the Sources section.
2. **Verify each claim.** For every factual claim with a footnote, confirm that the cited source actually supports the claim. Check names, numbers, dates, and roles.
3. **Check for unsourced claims.** Read through the entire profile looking for any factual statement without a citation. Either add a citation or remove the claim.
4. **Validate the inferred thesis.** Does the portfolio table actually support the percentage breakdowns and patterns described? Recalculate if needed.
5. **Check quote accuracy.** Verify that every quote in "In Their Own Words" and "What Founders Say" matches the cited source exactly.
6. **Cross-reference the frontmatter.** Ensure `stage_focus`, `sector_focus`, `check_size`, and other frontmatter fields are consistent with the profile body.

### After Review

- **If clean:** Set `status: published` in the frontmatter. Commit with message like "Review passed: publish jane-smith profile".
- **If issues found:** Set `status: flagged` in the frontmatter and add a `review_notes` field:

```yaml
status: flagged
review_notes: |
  - Claim about fund size in About section not supported by cited source [^2]
  - Quote in "What Founders Say" could not be verified at source URL [^8]
  - Inferred thesis sector percentages don't add up (total is 105%)
```

Commit the flagged profile so the issues are tracked. These can be resolved in a subsequent research pass.

## Quality Standards

In priority order:

1. **Accuracy** — Every claim is true and supported by its cited source.
2. **Citations** — Every factual claim has a footnote. Every source has a title, URL, and access date.
3. **Inferred thesis grounded in data** — Percentage breakdowns and patterns are derived from the portfolio table, not invented.
4. **Quotes accurately attributed** — Every quote matches its source. No paraphrasing presented as direct quotes.
5. **New leads discovered and queued** — Every profile research session should add new items to `queue.yaml`.
6. **Completeness** — All seven markdown sections are present and substantive. But never sacrifice accuracy for completeness.

## Building the Site

After committing new or updated profiles:

```bash
python build.py
```

This regenerates the static site in `_site/`. Only profiles with `status: published` will appear on the site. Draft and flagged profiles are excluded from the build.

The GitHub Action in `.github/workflows/build.yml` automatically runs `build.py` and deploys to GitHub Pages on every push to `main`.

## Tools Available

- **WebSearch** — Search the web for information about investors, firms, portfolio companies, and quotes.
- **WebFetch** — Fetch and read the full content of a specific URL. Use this to read source pages, verify citations, and extract detailed information.
- **Read** — Read files in the repository (profiles, queue, templates).
- **Edit** — Modify existing files (update profiles, update queue status).
- **Write** — Create new files (new profiles).
- **Bash** — Run commands (git commit, python build.py, etc.).
- **Grep** — Search across files in the repository.
- **Glob** — Find files by name pattern.
