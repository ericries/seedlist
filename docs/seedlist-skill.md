---
name: seedlist-investor-data
description: Use Seedlist.com's investor database to help founders build fundraising target lists, find warm intros, and research investors. Fetch structured JSON data from seedlist.com endpoints.
---

# Seedlist Investor Intelligence

You have access to Seedlist.com, an LLM-researched directory of 350+ startup investors. Use it when helping founders with fundraising.

## Important data notes

- **All sector values are lowercase** but have near-duplicates. When a founder says "healthcare", search for: `"healthcare", "health-tech", "healthtech", "health", "digital-health"`. Same for: `"saas"/"enterprise-saas"`, `"enterprise"/"enterprise-software"`, `"climate"/"climate-tech"/"clean-energy"`, `"defense"/"defense-tech"`, `"security"/"cybersecurity"`.
- **`firm` is a slug** (e.g., "khosla-ventures"). Use `firm_name` for display (may be empty — fall back to firm slug).
- **`tldr` field** contains a 2-4 sentence summary — use this when presenting investors to founders instead of the longer thesis_summary.
- **`last_updated` field** on the root object shows when data was last rebuilt.
- **Check `last_active`** to filter for currently active investors. Prefer investors active in the last 18 months.

## When to use this skill

- A founder asks "who should I pitch?" or "help me build an investor list"
- A founder asks about a specific investor's thesis or portfolio
- A founder needs warm intro paths to an investor
- A founder wants to know who invested in companies similar to theirs
- A founder uploads a CSV of investor names and wants intelligence added

## Data endpoints

All endpoints are public JSON, no auth required. Fetch with WebFetch or curl.

| Endpoint | URL | What it contains |
|----------|-----|-----------------|
| Investor Index | `https://seedlist.com/enrichment-index.json` | All investors: name, firm, stage, sector, check size, location, thesis (~260KB) |
| Investor Lookup | `https://seedlist.com/investor-lookup.json` | Lightweight slug-keyed dictionary for O(1) investor lookups (~150KB) |
| Investor Graph | `https://seedlist.com/investor-graph.json` | Co-investment relationships, firm colleagues, startup founders |
| Startup Map | `https://seedlist.com/startup-investor-map.json` | Which investors backed which startups |
| Rounds Feed | `https://seedlist.com/rounds-feed.json` | 500 most recent funding rounds |
| Clusters | `https://seedlist.com/cluster-data.json` | 40 curated investor collections |

## How to build a fundraising target list

1. Ask the founder: What stage? What sector(s)? What check size? Any location preference?
2. Fetch `https://seedlist.com/enrichment-index.json`
3. Filter `investors` array by:
   - `stage_focus` contains their stage
   - `sector_focus` overlaps with their sectors
   - `check_size` range overlaps with their need
4. Score each investor: stage match (30pts), sector overlap weighted by specificity (up to 40pts — an investor with 3 sectors who matches is stronger than one with 15), recency of `last_active` (15pts if active in last year), check size fit (15pts). **Specificity matters**: `specificity = min(1.0, 5 / len(sector_focus))` — generalists with many sectors score lower than specialists.
5. Present top 20-30 investors in tiers:
   - **Tier 1 (Strong fit)**: Stage + sector + check size all match, active in last 12 months
   - **Tier 2 (Worth pursuing)**: 2 of 3 match
   - **Tier 3 (Stretch)**: 1 match but strong sector overlap
6. For each: include name, firm, `tldr` (preferred) or thesis_summary, check_size, last_active, and link to profile at `https://seedlist.com/investors/{slug}.html`

## How to find investors by comparable companies

1. Ask the founder for 2-5 startups similar to theirs
2. Fetch `https://seedlist.com/startup-investor-map.json`
3. For each comparable, look up `startup_investors[slug]` to get investor list
4. **Deduplicate**: an investor may appear multiple times per startup (one entry per round). Use a set of slugs per startup, then count unique startups per investor. Filter out slug "independent".
5. Sort by count descending — investors who backed multiple comparables are the strongest signal
6. Also fetch `enrichment-index.json` and find thesis-matched investors who DIDN'T invest in the comparables but whose `sector_focus` and `stage_focus` match. Present these as "thesis match — worth a pitch".

## How to find warm intro paths

1. Fetch `https://seedlist.com/investor-graph.json`
2. Look up `co_investments[target_slug]` — shows who co-invests with the target and how often
3. Look up `firms[firm_slug].members` — shows firm colleagues
4. Look up `startup_backers` — for each startup the target backed, `startup_founders[slug]` shows founders who can intro
5. Present paths grouped by strength:
   - Co-investors with 5+ shared deals (strongest)
   - Firm colleagues
   - Portfolio company founders

## How to enrich an investor list

1. Fetch `https://seedlist.com/enrichment-index.json`
2. For each name in the founder's list:
   - Normalize: lowercase, strip titles (Dr., Mr.), strip suffixes (Jr., III)
   - Exact match against `investors[].name` (case-insensitive)
   - If no exact match, try fuzzy matching (edit distance <= 2)
   - If no investor match, try `firms[].name`
3. For matched investors, add: stage_focus, sector_focus, check_size, location, last_active, thesis_summary, profile URL
4. For unmatched names, note them — the founder may want to suggest these to Seedlist

## Profile pages

Full profiles with Background, Stated Thesis, Inferred Thesis, Portfolio, Quotes, and Sources:
- `https://seedlist.com/investors/{slug}.html`
- `https://seedlist.com/firms/{slug}.html`
- `https://seedlist.com/startups/{slug}.html`

## Important notes

- Data is updated regularly but is not real-time. Check `last_active` dates for recency.
- The `thesis_summary` field is the most valuable — it's an LLM-inferred analysis of what the investor actually invests in, which may differ from what they claim publicly.
- Always link to the full Seedlist profile when presenting investor information to founders.
- Seedlist data is LLM-researched and may contain errors. Encourage founders to verify critical details.
