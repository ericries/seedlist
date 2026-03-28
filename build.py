#!/usr/bin/env python3
"""Static site generator for seedlist.com.

Reads markdown profiles from data/, renders HTML with Jinja2 templates,
and outputs a complete static site to _site/.
"""

import json
import os
import re
import shutil
from pathlib import Path

import frontmatter
import markdown
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "_site"


def load_profiles(subdir):
    """Load all markdown profiles from a data subdirectory."""
    profiles = []
    data_path = DATA_DIR / subdir
    if not data_path.exists():
        return profiles
    for md_file in sorted(data_path.glob("*.md")):
        post = frontmatter.load(md_file)
        profile = dict(post.metadata)
        profile["content"] = markdown.markdown(
            post.content,
            extensions=["tables", "footnotes", "smarty"],
        )
        profiles.append(profile)
    return profiles


def filter_published(profiles):
    """Return only profiles with status: published."""
    return [p for p in profiles if p.get("status") == "published"]


def slugify(text):
    """Convert text to a URL-safe slug."""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def collect_values(profiles, key):
    """Collect all unique values for a list-type field across profiles."""
    values = set()
    for p in profiles:
        for v in p.get(key, []):
            values.add(v)
    return sorted(values)


def build_search_index(investors, firms, startups):
    """Build a JSON search index for client-side search."""
    entries = []
    for p in investors:
        text_parts = [p.get("name", ""), p.get("firm", ""), p.get("role", ""),
                      p.get("location", "")] + (p.get("stage_focus") or []) + (p.get("sector_focus") or [])
        text_parts = [str(t) for t in text_parts if t]  # filter None, coerce to str
        entries.append({
            "name": p.get("name", ""),
            "type": "investor",
            "slug": p.get("slug", ""),
            "firm": p.get("firm") or "",
            "role": p.get("role") or "",
            "location": p.get("location") or "",
            "stages": p.get("stage_focus") or [],
            "sectors": p.get("sector_focus") or [],
            "text": " ".join(text_parts),
            "url": f"/investors/{p.get('slug', '')}.html",
        })
    for p in firms:
        text_parts = [p.get("name", ""), p.get("location", "")] + (p.get("stage_focus") or []) + (p.get("sector_focus") or [])
        text_parts = [t for t in text_parts if t]
        entries.append({
            "name": p.get("name", ""),
            "type": "firm",
            "slug": p.get("slug", ""),
            "location": p.get("location") or "",
            "stages": p.get("stage_focus") or [],
            "sectors": p.get("sector_focus") or [],
            "text": " ".join(text_parts),
            "url": f"/firms/{p.get('slug', '')}.html",
        })
    for p in startups:
        text_parts = [p.get("name", ""), p.get("location", "")] + (p.get("sector") or [])
        text_parts = [t for t in text_parts if t]
        entries.append({
            "name": p.get("name", ""),
            "type": "startup",
            "slug": p.get("slug", ""),
            "location": p.get("location") or "",
            "sectors": p.get("sector") or [],
            "stage_latest": p.get("stage_latest") or "",
            "text": " ".join(text_parts),
            "url": f"/startups/{p.get('slug', '')}.html",
        })
    return entries


def build_enrichment_index(investors, firms, queue_path):
    """Build a JSON enrichment index for the client-side /enrich page."""
    index = {"investors": [], "firms": [], "queued": []}

    for p in investors:
        # Extract inferred thesis summary from rendered HTML (strip tags)
        thesis_summary = ""
        content = p.get("content", "")
        # Find the Inferred Thesis section in the HTML
        m = re.search(r'<h2[^>]*>Inferred Thesis</h2>(.*?)(?=<h2|$)', content, re.DOTALL)
        if m:
            # Strip HTML tags, decode entities, get first 200 chars
            import html as html_mod
            text = re.sub(r'<[^>]+>', ' ', m.group(1))
            text = re.sub(r'\s+', ' ', text).strip()
            text = html_mod.unescape(text)
            thesis_summary = text[:200]

        lvi = p.get("last_verified_investment")
        last_active = ""
        if isinstance(lvi, dict):
            last_active = str(lvi.get("date", ""))

        index["investors"].append({
            "name": p.get("name", ""),
            "slug": p.get("slug", ""),
            "firm": p.get("firm", ""),
            "firm_name": "",  # will be filled in below
            "role": p.get("role", ""),
            "location": p.get("location", ""),
            "stage_focus": p.get("stage_focus", []),
            "sector_focus": [s.lower() for s in (p.get("sector_focus") or [])],
            "check_size": p.get("check_size", ""),
            "last_active": last_active,
            "status": p.get("status", ""),
            "thesis_summary": thesis_summary,
            "tldr": p.get("tldr", ""),
        })

    firm_name_lookup = {}
    for p in firms:
        firm_name_lookup[p.get("slug", "")] = p.get("name", "")
        index["firms"].append({
            "name": p.get("name", ""),
            "slug": p.get("slug", ""),
            "location": p.get("location", ""),
            "stage_focus": p.get("stage_focus", []),
            "sector_focus": p.get("sector_focus", []),
            "fund_size": p.get("fund_size", ""),
            "status": p.get("status", ""),
        })

    # Fill in firm_name for investors
    for inv in index["investors"]:
        inv["firm_name"] = firm_name_lookup.get(inv["firm"], "")

    # Load queued items
    if queue_path.exists():
        import yaml
        with open(queue_path) as f:
            q = yaml.safe_load(f)
        for item in q.get("queue", []):
            if item.get("status") in ("pending", "in_progress"):
                index["queued"].append({
                    "name": item.get("name", ""),
                    "type": item.get("type", ""),
                    "firm": item.get("firm", ""),
                })

    return index


def build_investor_graph(investors, firms, startups, clusters_data):
    """Build an investor connection graph JSON for the 'Paths to' feature.

    Returns a dict with:
      - firms: firm slug -> {name, members[]}
      - co_investments: investor slug -> {other slug -> {count, companies[]}}
      - startup_backers: startup slug -> [investor/firm slugs]
      - investor_names: slug -> display name
      - investor_firms: slug -> firm name (display)
      - collections: slug -> [collection names]
    """
    from collections import defaultdict

    firm_lookup = {f["slug"]: f for f in firms}
    investor_lookup = {i["slug"]: i for i in investors}

    # 1. Build firms -> members map
    graph_firms = {}
    for inv in investors:
        firm_slug = inv.get("firm", "")
        if not firm_slug:
            continue
        if firm_slug not in graph_firms:
            firm_data = firm_lookup.get(firm_slug)
            firm_name = firm_data["name"] if firm_data else firm_slug
            graph_firms[firm_slug] = {"name": firm_name, "members": []}
        if inv["slug"] not in graph_firms[firm_slug]["members"]:
            graph_firms[firm_slug]["members"].append(inv["slug"])

    # 2. Build investor -> set of portfolio company slugs from investor markdown
    investor_companies = defaultdict(set)
    inv_data_path = DATA_DIR / "investors"
    if inv_data_path.exists():
        for md_file in sorted(inv_data_path.glob("*.md")):
            post = frontmatter.load(md_file)
            meta = dict(post.metadata)
            if meta.get("status") != "published":
                continue
            slug = meta.get("slug", "")
            if not slug:
                continue
            # Parse portfolio table from raw markdown
            raw = post.content
            in_portfolio = False
            for line in raw.split("\n"):
                stripped = line.strip()
                if stripped.startswith("## Portfolio"):
                    in_portfolio = True
                    continue
                if in_portfolio and stripped.startswith("## "):
                    break
                if in_portfolio and stripped.startswith("|") and not stripped.startswith("|--") and not stripped.startswith("| Company"):
                    parts = [p.strip() for p in stripped.split("|")]
                    if len(parts) >= 2:
                        company_name = parts[1]
                        if company_name and company_name != "Company":
                            company_slug = re.sub(r'[^a-z0-9]+', '-', company_name.lower()).strip('-')
                            investor_companies[slug].add(company_slug)

    # 3. Also extract from startup profiles (investors/firms listed in frontmatter)
    startup_backers = {}
    startup_names = {}
    startup_founders = {}  # slug -> [{name, role}]
    # Track which startups each investor backed (from startup frontmatter)
    investor_startups_from_fm = defaultdict(set)
    for s in startups:
        s_slug = s.get("slug", "")
        if not s_slug:
            continue
        startup_names[s_slug] = s.get("name", s_slug)
        # Extract founders
        founders = []
        for f in (s.get("founders") or []):
            fname = f.get("name", "")
            frole = f.get("role", "")
            if fname:
                founders.append({"name": fname, "role": frole})
        if founders:
            startup_founders[s_slug] = founders
        backers = []
        for inv_entry in (s.get("investors") or []):
            inv_slug = inv_entry.get("slug", "")
            if inv_slug:
                backers.append(inv_slug)
                investor_startups_from_fm[inv_slug].add(s_slug)
        for firm_entry in (s.get("firms") or []):
            firm_slug = firm_entry.get("slug", "")
            if firm_slug:
                backers.append(firm_slug)
        if backers:
            startup_backers[s_slug] = backers

    # Merge startup frontmatter data into investor_companies
    for inv_slug, startup_slugs in investor_startups_from_fm.items():
        investor_companies[inv_slug].update(startup_slugs)

    # 4. Compute co-investment counts between all investor pairs
    # Build company -> set of investors
    company_investors = defaultdict(set)
    for inv_slug, companies in investor_companies.items():
        for co in companies:
            company_investors[co].add(inv_slug)

    # Now compute pairwise co-investments
    co_investments = defaultdict(lambda: defaultdict(lambda: {"count": 0, "companies": []}))
    for company, inv_set in company_investors.items():
        inv_list = sorted(inv_set)
        for i in range(len(inv_list)):
            for j in range(i + 1, len(inv_list)):
                a, b = inv_list[i], inv_list[j]
                co_investments[a][b]["count"] += 1
                co_investments[a][b]["companies"].append(company)
                co_investments[b][a]["count"] += 1
                co_investments[b][a]["companies"].append(company)

    # Filter to count >= 2, cap companies at 8 per pair
    filtered_co = {}
    for inv_slug, peers in co_investments.items():
        inv_peers = {}
        for peer_slug, data in peers.items():
            if data["count"] >= 2:
                companies = sorted(data["companies"])[:8]
                inv_peers[peer_slug] = {"count": data["count"], "companies": companies}
        if inv_peers:
            filtered_co[inv_slug] = inv_peers

    # 5. Build investor names and firms maps
    investor_names = {}
    investor_firms_map = {}
    for inv in investors:
        slug = inv.get("slug", "")
        investor_names[slug] = inv.get("name", slug)
        firm_slug = inv.get("firm", "")
        firm_data = firm_lookup.get(firm_slug)
        investor_firms_map[slug] = firm_data["name"] if firm_data else ""

    # 6. Build collections map from curated_collections
    collections_map = {}
    curated = clusters_data.get("curated_collections", [])
    for col in curated:
        col_name = col.get("name", "")
        for member in col.get("members", []):
            m_slug = member.get("slug", "")
            if m_slug:
                if m_slug not in collections_map:
                    collections_map[m_slug] = []
                collections_map[m_slug].append(col_name)

    return {
        "firms": graph_firms,
        "co_investments": filtered_co,
        "startup_backers": startup_backers,
        "startup_names": startup_names,
        "startup_founders": startup_founders,
        "investor_names": investor_names,
        "investor_firms": investor_firms_map,
        "collections": collections_map,
    }


def build_startup_investor_map(startups, investor_lookup, firm_lookup):
    """Build a JSON map of startups to their investors for the comparable companies finder."""
    startup_list = []
    startup_investors = {}

    for s in startups:
        slug = s.get("slug", "")
        if not slug:
            continue
        startup_list.append({
            "slug": slug,
            "name": s.get("name", ""),
            "sector": s.get("sector", []),
            "stage": s.get("stage_latest", ""),
        })

        investors_for_startup = []

        # Add individual investors
        for inv_entry in (s.get("investors") or []):
            inv_slug = inv_entry.get("slug", "")
            inv_data = investor_lookup.get(inv_slug, {})
            inv_name = inv_data.get("name", inv_slug)
            inv_firm = inv_data.get("firm", "")
            firm_name = firm_lookup.get(inv_firm, {}).get("name", "") if inv_firm else ""
            has_profile = inv_slug in investor_lookup
            investors_for_startup.append({
                "slug": inv_slug,
                "name": inv_name,
                "type": "individual",
                "firm": firm_name or inv_firm,
                "round": inv_entry.get("round", ""),
                "year": inv_entry.get("year", ""),
                "has_profile": has_profile,
            })

        # Add firms
        for firm_entry in (s.get("firms") or []):
            firm_slug = firm_entry.get("slug", "")
            firm_data = firm_lookup.get(firm_slug, {})
            firm_name = firm_data.get("name", firm_slug)
            has_profile = firm_slug in firm_lookup
            investors_for_startup.append({
                "slug": firm_slug,
                "name": firm_name,
                "type": "firm",
                "firm": "",
                "round": firm_entry.get("round", ""),
                "year": firm_entry.get("year", ""),
                "has_profile": has_profile,
            })

        startup_investors[slug] = investors_for_startup

    return {
        "startups": startup_list,
        "startup_investors": startup_investors,
    }


MONTH_MAP = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
    'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
    'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'june': '06', 'july': '07', 'august': '08', 'september': '09',
    'october': '10', 'november': '11', 'december': '12',
}

ROUND_KEYWORDS = {'seed', 'series', 'angel', 'pre-seed', 'growth',
                  'convertible', 'bridge', 'extension', 'tender', 'secondary', 'debt'}

SKIP_ROUND_KEYWORDS = {'ipo', 'spac', 'acquisition', 'acquired', 'public markets', 'public'}


def parse_date(text):
    """Try to extract a sortable date string from various formats."""
    text = text.strip()
    # YYYY-MM-DD
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # YYYY-MM
    m = re.match(r'^(\d{4})-(\d{2})$', text)
    if m:
        return text
    # Month Day, YYYY or Mon Day, YYYY (e.g., "March 15, 2026")
    m = re.match(r'^(\w+)\s+(\d{1,2}),?\s+(\d{4})$', text)
    if m:
        month = MONTH_MAP.get(m.group(1).lower())
        if month:
            return f"{m.group(3)}-{month}-{int(m.group(2)):02d}"
    # Month YYYY or Mon YYYY
    m = re.match(r'^(\w+)\s+(\d{4})$', text)
    if m:
        month = MONTH_MAP.get(m.group(1).lower())
        if month:
            return f"{m.group(2)}-{month}"
    # Just YYYY
    m = re.match(r'^~?(\d{4})$', text)
    if m:
        return m.group(1)
    return None


def is_round_type(text):
    """Check if text looks like a funding round type."""
    lower = text.lower().strip()
    return any(kw in lower for kw in ROUND_KEYWORDS)


def is_skip_round(text):
    """Check if this round type should be excluded from the feed."""
    lower = text.lower().strip()
    return any(kw in lower for kw in SKIP_ROUND_KEYWORDS)


def is_amount(text):
    """Check if text looks like a dollar amount."""
    return '$' in text or text.strip().lower() in ('undisclosed', '')


def parse_funding_table(raw_content):
    """Parse a Funding History markdown table into a list of round dicts.

    Returns list of dicts with keys: date, round, amount, lead.
    Handles varying column orders by detecting column types from content.
    """
    rounds = []
    in_funding = False
    header_cols = []

    for line in raw_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## Funding History"):
            in_funding = True
            continue
        if in_funding and stripped.startswith("## "):
            break
        if not in_funding or not stripped.startswith("|"):
            continue

        cells = [c.strip() for c in stripped.split("|")]
        # Remove empty first/last from leading/trailing |
        cells = [c for c in cells if c or c == ""]
        if not cells:
            continue

        # Detect header row
        if not header_cols:
            # Check if this is a header (contains words like Date, Round, Amount)
            header_text = " ".join(cells).lower()
            if any(kw in header_text for kw in ['date', 'round', 'amount', 'lead', 'investor', 'valuation']):
                header_cols = [c.lower().strip() for c in cells]
                continue
            else:
                continue

        # Skip separator rows
        if all(set(c.strip()) <= {'-', ':', ' '} for c in cells):
            continue

        # Map cells to fields using header
        row = {}
        for i, col_name in enumerate(header_cols):
            if i < len(cells):
                val = cells[i].strip()
                # Strip footnote refs like [^1]
                val = re.sub(r'\[\^\d+\]', '', val).strip()
                if not val or val == '':
                    continue

                if 'date' in col_name:
                    row['date'] = val
                elif 'round' in col_name:
                    row['round'] = val
                elif 'amount' in col_name:
                    row['amount'] = val
                elif 'lead' in col_name or 'investor' in col_name:
                    if 'lead' not in row:
                        row['lead'] = val
                    # If there's a separate co-investors column, append
                    elif 'co' in col_name:
                        if row['lead'] and val:
                            row['lead'] = row['lead'] + ", " + val

        # If no header-based mapping, try auto-detect from cell content
        if not row.get('round') and not row.get('date'):
            for cell in cells:
                cell_clean = re.sub(r'\[\^\d+\]', '', cell).strip()
                if not cell_clean:
                    continue
                if parse_date(cell_clean) and 'date' not in row:
                    row['date'] = cell_clean
                elif is_round_type(cell_clean) and 'round' not in row:
                    row['round'] = cell_clean
                elif is_amount(cell_clean) and 'amount' not in row:
                    row['amount'] = cell_clean
                elif 'lead' not in row:
                    row['lead'] = cell_clean

        if row.get('round') or row.get('date'):
            rounds.append(row)

    return rounds


def build_rounds_feed(startups):
    """Build a reverse-chronological feed of startup funding rounds.

    Extracts rounds from two sources per startup:
    1. Frontmatter investors/firms arrays (reliable: has year, round, slug)
    2. Funding History table (has amounts, dates, leads)

    Returns a sorted list of round dicts ready for JSON output.
    """
    all_rounds = []
    startup_data_path = DATA_DIR / "startups"

    for startup in startups:
        slug = startup.get("slug", "")
        name = startup.get("name", "")
        sector = startup.get("sector", [])
        if not slug or not name:
            continue

        # Source 1: frontmatter investors + firms arrays
        fm_rounds = {}  # key: (round_type_lower, year) -> dict
        for entry in (startup.get("investors") or []) + (startup.get("firms") or []):
            round_type = str(entry.get("round", "")).strip()
            year = entry.get("year")
            if not year:
                continue
            year_str = str(year).lstrip("~")
            # Use precise date from frontmatter if available
            entry_date = str(entry.get("date", "")).strip() if entry.get("date") else ""
            # Skip non-fundraising rounds
            if is_skip_round(round_type):
                continue
            # Normalize round key — strip year-like prefixes and amounts
            round_clean = re.sub(r'^\~?\d{4}$', '', round_type).strip()
            if not round_clean:
                round_clean = "Unknown"
            # Normalize key: replace dashes with spaces for consistent matching
            round_norm = round_clean.lower().replace('-', ' ')
            key = (round_norm, year_str)
            if key not in fm_rounds:
                fm_rounds[key] = {
                    "company": name,
                    "company_slug": slug,
                    "date": entry_date if entry_date else year_str,
                    "round": round_clean,
                    "amount": "",
                    "lead": "",
                    "investors": [],
                    "sector": sector,
                }
            inv_slug = entry.get("slug", "")
            if inv_slug and inv_slug not in fm_rounds[key]["investors"]:
                fm_rounds[key]["investors"].append(inv_slug)

        # Source 2: Funding History table from raw markdown
        md_path = startup_data_path / f"{slug}.md"
        table_rounds = {}  # key: (round_type_lower, year) -> dict
        if md_path.exists():
            post = frontmatter.load(md_path)
            parsed = parse_funding_table(post.content)
            for row in parsed:
                round_type = row.get("round", "").strip()
                if is_skip_round(round_type):
                    continue
                date_str = parse_date(row.get("date", ""))
                if not date_str and not round_type:
                    continue
                # Extract year for matching
                year_for_key = ""
                if date_str:
                    year_for_key = date_str[:4]
                round_key = round_type.lower().replace('-', ' ') if round_type else "unknown"
                key = (round_key, year_for_key)
                table_rounds[key] = {
                    "date": date_str or "",
                    "round": round_type,
                    "amount": row.get("amount", ""),
                    "lead": row.get("lead", ""),
                }

        # Merge: start with frontmatter rounds, enrich from table
        merged = {}
        for key, fm_data in fm_rounds.items():
            merged[key] = dict(fm_data)
            # Try to find matching table row
            tbl = table_rounds.get(key)
            if tbl:
                # Prefer table date (more precise, e.g. YYYY-MM vs YYYY)
                if tbl["date"] and len(tbl["date"]) > len(merged[key]["date"]):
                    merged[key]["date"] = tbl["date"]
                if tbl["amount"]:
                    merged[key]["amount"] = tbl["amount"]
                if tbl["lead"]:
                    merged[key]["lead"] = tbl["lead"]
                if tbl["round"]:
                    merged[key]["round"] = tbl["round"]

        # Add table-only rounds not in frontmatter
        for key, tbl_data in table_rounds.items():
            if key not in merged:
                if is_skip_round(tbl_data.get("round", "")):
                    continue
                merged[key] = {
                    "company": name,
                    "company_slug": slug,
                    "date": tbl_data["date"],
                    "round": tbl_data["round"],
                    "amount": tbl_data["amount"],
                    "lead": tbl_data["lead"],
                    "investors": [],
                    "sector": sector,
                }

        for r in merged.values():
            # Must have at least a company and a year
            if not r.get("date"):
                continue
            all_rounds.append(r)

    # Deduplicate rounds: same company + same normalized round with different
    # date precision. Keep the entry with more precise date, merge investors.
    dedup = {}
    for r in all_rounds:
        # Normalize: strip punctuation, replace "plus" with "+", collapse whitespace
        norm_round = r.get("round", "").lower()
        norm_round = norm_round.replace("-plus-", " ").replace("plus", " ").replace("+", " ")
        norm_round = re.sub(r'[^a-z0-9 ]', ' ', norm_round).strip()
        norm_round = re.sub(r'\s+', ' ', norm_round)
        dedup_key = (r["company_slug"], norm_round)
        if dedup_key in dedup:
            existing = dedup[dedup_key]
            # Keep the more precise date
            if len(r.get("date", "")) > len(existing.get("date", "")):
                existing["date"] = r["date"]
            # Merge investors
            for inv in r.get("investors", []):
                if inv not in existing.get("investors", []):
                    existing.setdefault("investors", []).append(inv)
            # Fill missing amount/lead
            if r.get("amount") and not existing.get("amount"):
                existing["amount"] = r["amount"]
            if r.get("lead") and not existing.get("lead"):
                existing["lead"] = r["lead"]
        else:
            dedup[dedup_key] = r
    all_rounds = list(dedup.values())

    # Build sort key: pad YYYY to YYYY-00-00, YYYY-MM to YYYY-MM-00
    def sort_key(r):
        d = r.get("date", "")
        if len(d) == 4:  # YYYY
            return d + "-00-00"
        elif len(d) == 7:  # YYYY-MM
            return d + "-00"
        return d

    all_rounds.sort(key=sort_key, reverse=True)

    # Cap at 500
    all_rounds = all_rounds[:500]

    # Build final output (drop investors list of slugs for cleaner JSON,
    # or keep them for potential linking)
    def clean_dash(val):
        """Strip placeholder dashes from amount/lead fields."""
        if not val:
            return ""
        stripped = val.strip()
        if stripped in ("—", "–", "-", "N/A", "n/a", "Unknown", "unknown", "Undisclosed", "undisclosed"):
            return ""
        return stripped

    def prettify_round(name):
        """Clean up round names: 'series-a' -> 'Series A'."""
        if not name:
            return name
        # If it looks like a slug (has dashes, no spaces, all lowercase), convert
        if '-' in name and ' ' not in name and name == name.lower():
            name = name.replace('-', ' ')
            # Title-case, but keep single letters uppercase
            parts = name.split()
            result = []
            for p in parts:
                if len(p) <= 2:
                    result.append(p.upper())
                else:
                    result.append(p.capitalize())
            return ' '.join(result)
        return name

    output = []
    for r in all_rounds:
        output.append({
            "company": r["company"],
            "company_slug": r["company_slug"],
            "date": r["date"],
            "round": prettify_round(r["round"]),
            "amount": clean_dash(r.get("amount", "")),
            "lead": clean_dash(r.get("lead", "")),
            "investors": r.get("investors", []),
            "sector": r.get("sector", []),
            "sort_key": sort_key(r),
        })

    return output


def linkify_profile_content(html, startup_lookup, investor_lookup, firm_lookup):
    """Auto-link known entity names in table cells to their profile pages."""
    if not html:
        return html

    # Build name->url maps for all three entity types
    name_map = {}
    for s in startup_lookup.values():
        name = s.get("name", "")
        if name and len(name) > 2:
            name_map[name] = f"/startups/{s['slug']}.html"
    for i in investor_lookup.values():
        name = i.get("name", "")
        if name and len(name) > 2:
            name_map[name] = f"/investors/{i['slug']}.html"
    for f in firm_lookup.values():
        name = f.get("name", "")
        if name and len(name) > 2:
            name_map[name] = f"/firms/{f['slug']}.html"

    # Sort by length descending to match longer names first
    sorted_names = sorted(name_map.keys(), key=len, reverse=True)

    def replace_in_td(match):
        td_content = match.group(1)
        # Don't double-link: skip if already contains <a
        if '<a ' in td_content:
            return match.group(0)
        for name in sorted_names:
            if name in td_content:
                td_content = td_content.replace(
                    name,
                    f'<a href="{name_map[name]}">{name}</a>',
                    1  # only first occurrence
                )
                break  # one link per cell
        return f'<td>{td_content}</td>'

    return re.sub(r'<td>(.*?)</td>', replace_in_td, html)


def build():
    """Build the static site."""
    # Clean output
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # Set up Jinja2
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["slugify"] = slugify

    def format_date(date_str):
        """Format YYYY-MM-DD or YYYY-MM or YYYY to human-readable."""
        if not date_str:
            return ""
        s = str(date_str).strip()
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        parts = s.split("-")
        if len(parts) == 3:  # YYYY-MM-DD
            try:
                return f"{months[int(parts[1])-1]} {int(parts[2])}, {parts[0]}"
            except (ValueError, IndexError):
                return s
        if len(parts) == 2:  # YYYY-MM
            try:
                return f"{months[int(parts[1])-1]} {parts[0]}"
            except (ValueError, IndexError):
                return s
        return s  # YYYY or other
    env.filters["format_date"] = format_date

    # Load all profiles
    all_investors = load_profiles("investors")
    all_firms = load_profiles("firms")
    all_startups = load_profiles("startups")

    # Filter to published
    investors = filter_published(all_investors)
    firms = filter_published(all_firms)
    startups = filter_published(all_startups)

    # Load cluster data
    clusters_data = {}
    clusters_path = DATA_DIR / "clusters.json"
    if clusters_path.exists():
        with open(clusters_path) as f:
            clusters_data = json.load(f)

    # Build lookups for cross-linking
    firm_lookup = {f["slug"]: f for f in firms}
    investor_lookup = {i["slug"]: i for i in investors}
    startup_lookup = {s["slug"]: s for s in startups}

    # Auto-link entity names in profile body content
    for p in investors + firms + startups:
        p["content"] = linkify_profile_content(
            p.get("content", ""), startup_lookup, investor_lookup, firm_lookup
        )

    # Build cluster lookup for investor pages
    similar_investors_map = clusters_data.get("similar_investors", {})
    investor_clusters_map = clusters_data.get("investor_clusters", {})
    clusters_list = clusters_data.get("algo_clusters", clusters_data.get("clusters", []))
    cluster_by_id = {c["id"]: c for c in clusters_list}
    curated_collections = clusters_data.get("curated_collections", [])

    # Render investor pages
    investor_template = env.get_template("investor.html")
    (OUTPUT_DIR / "investors").mkdir(parents=True, exist_ok=True)
    for profile in investors:
        profile["firm_data"] = firm_lookup.get(profile.get("firm", ""))

        # Resolve similar investors
        slug = profile.get("slug", "")
        similar_slugs = similar_investors_map.get(slug, [])
        similar = []
        for s in similar_slugs:
            inv = investor_lookup.get(s)
            if inv:
                inv_copy = dict(inv)
                inv_copy["firm_name"] = firm_lookup.get(inv.get("firm", ""), {}).get("name", "")
                similar.append(inv_copy)
        # Resolve investor cluster
        cluster_id = investor_clusters_map.get(slug)
        inv_cluster = cluster_by_id.get(cluster_id) if cluster_id is not None else None

        # Find curated collections this investor belongs to
        inv_collections = [
            col for col in curated_collections
            if any(m.get("slug") == slug for m in col.get("members", []))
        ]

        html = investor_template.render(
            profile=profile,
            similar_investors=similar,
            investor_cluster=inv_cluster,
            investor_collections=inv_collections,
            startup_lookup=startup_lookup,
        )
        out_path = OUTPUT_DIR / "investors" / f"{profile['slug']}.html"
        out_path.write_text(html)

    # Render firm pages
    firm_template = env.get_template("firm.html")
    (OUTPUT_DIR / "firms").mkdir(parents=True, exist_ok=True)
    for profile in firms:
        # Attach investor data for team members
        profile["team_profiles"] = []
        for member in profile.get("team", []):
            for inv in investors:
                if inv["slug"] == member["slug"]:
                    profile["team_profiles"].append(inv)
                    break
        html = firm_template.render(profile=profile, investor_lookup=investor_lookup)
        out_path = OUTPUT_DIR / "firms" / f"{profile['slug']}.html"
        out_path.write_text(html)

    # Render startup pages
    startup_template = env.get_template("startup.html")
    (OUTPUT_DIR / "startups").mkdir(parents=True, exist_ok=True)
    for profile in startups:
        html = startup_template.render(
            profile=profile,
            investor_lookup=investor_lookup,
            firm_lookup=firm_lookup,
        )
        out_path = OUTPUT_DIR / "startups" / f"{profile['slug']}.html"
        out_path.write_text(html)

    # Sort investors: most recent verified investment first, profiles without dates last
    def investor_recency_key(p):
        date = str((p.get("last_verified_investment") or {}).get("date", ""))
        if date:
            return (0, date)  # has date — sort ascending by group, descending by date
        return (1, "")

    investors_sorted = sorted(investors, key=investor_recency_key)
    # Two-pass: first separate dated/undated, then reverse dated group
    dated = [p for p in investors if (p.get("last_verified_investment") or {}).get("date")]
    undated = [p for p in investors if not (p.get("last_verified_investment") or {}).get("date")]
    dated.sort(key=lambda p: str((p.get("last_verified_investment") or {}).get("date", "")).lstrip("~"), reverse=True)
    investors_sorted = dated + undated

    # Location normalization for investor filtering
    def normalize_location(loc):
        if not loc:
            return ""
        loc_lower = loc.lower()
        sf_keywords = ["san francisco", "menlo park", "palo alto", "mountain view",
                        "woodside", "redwood city", "atherton", "bay area",
                        "saratoga", "cupertino", "sunnyvale", "san mateo",
                        "portola valley", "los altos", "burlingame", "hillsborough"]
        for kw in sf_keywords:
            if kw in loc_lower:
                return "sf-bay-area"
        if "new york" in loc_lower:
            return "nyc"
        if "los angeles" in loc_lower:
            return "la"
        if "boston" in loc_lower or "cambridge" in loc_lower:
            return "boston"
        return ""

    # Prepare investor data for filtered listing
    for p in investors_sorted:
        p["location_region"] = normalize_location(p.get("location", ""))
        lvi = p.get("last_verified_investment") or {}
        p["last_active"] = str(lvi.get("date", "")).lstrip("~") if lvi.get("date") else ""

    # Compute top sectors for filter dropdown
    sector_counts = {}
    for p in investors:
        for s in (p.get("sector_focus") or []):
            sl = s.lower()
            sector_counts[sl] = sector_counts.get(sl, 0) + 1
    top_sectors = [s for s, _ in sorted(sector_counts.items(), key=lambda x: -x[1])[:15]]

    # Generate listing pages
    listing_template = env.get_template("listing.html")
    investors_listing_template = env.get_template("investors_listing.html")

    # All investors (sorted by most recent investment) — uses dedicated filtered template
    html = investors_listing_template.render(profiles=investors_sorted, top_sectors=top_sectors)
    (OUTPUT_DIR / "investors" / "index.html").write_text(html)

    # Investor clusters / groups page
    all_groups = curated_collections  # single unified list
    if all_groups:
        clusters_template = env.get_template("clusters.html")
        html = clusters_template.render(
            groups=all_groups,
            total_investors=len(investors),
        )
        (OUTPUT_DIR / "investors" / "groups.html").write_text(html)

    # All firms
    html = listing_template.render(title="All Firms", profiles=firms, list_type="firm")
    (OUTPUT_DIR / "firms" / "index.html").write_text(html)

    # All startups
    html = listing_template.render(title="All Startups", profiles=startups, list_type="startup")
    (OUTPUT_DIR / "startups" / "index.html").write_text(html)

    # By stage — include investors, firms, and startups (startups use stage_latest)
    stages = collect_values(investors + firms, "stage_focus")
    (OUTPUT_DIR / "stage").mkdir(parents=True, exist_ok=True)
    for stage in stages:
        matched = [p for p in investors + firms if stage in p.get("stage_focus", [])]
        html = listing_template.render(title=f"Stage: {stage}", profiles=matched, list_type="mixed")
        (OUTPUT_DIR / "stage" / f"{slugify(stage)}.html").write_text(html)

    # By sector — include startups (they use "sector" field) alongside investors/firms ("sector_focus")
    all_for_sector = investors + firms + startups
    sector_set = set()
    for p in all_for_sector:
        for v in p.get("sector_focus", []):
            sector_set.add(v)
        for v in p.get("sector", []):
            sector_set.add(v)
    sectors = sorted(sector_set)
    (OUTPUT_DIR / "sector").mkdir(parents=True, exist_ok=True)
    for sector in sectors:
        matched = [p for p in all_for_sector
                    if sector in p.get("sector_focus", []) or sector in p.get("sector", [])]
        html = listing_template.render(title=f"Sector: {sector}", profiles=matched, list_type="mixed")
        (OUTPUT_DIR / "sector" / f"{slugify(sector)}.html").write_text(html)

    # Generate search index
    search_index = build_search_index(investors, firms, startups)
    (OUTPUT_DIR / "search-index.json").write_text(json.dumps(search_index, indent=2))

    # Generate enrichment index for /enrich page
    enrichment_index = build_enrichment_index(investors, firms, DATA_DIR / "queue.yaml")
    from datetime import datetime
    enrichment_index["last_updated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    (OUTPUT_DIR / "enrichment-index.json").write_text(json.dumps(enrichment_index))

    # Lightweight lookup endpoint for quick agent queries
    investor_lookup_data = {
        "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(enrichment_index["investors"]),
        "investors": {}
    }
    for inv in enrichment_index["investors"]:
        # Truncate tldr to first sentence or 120 chars to keep file small
        tldr = inv.get("tldr", "")
        if tldr:
            first_period = tldr.find(". ")
            if first_period > 0 and first_period < 150:
                tldr = tldr[:first_period + 1]
            elif len(tldr) > 120:
                tldr = tldr[:120].rsplit(" ", 1)[0] + "..."
        investor_lookup_data["investors"][inv["slug"]] = {
            "name": inv["name"],
            "firm": inv["firm_name"] or inv["firm"],
            "tldr": tldr,
            "check_size": inv.get("check_size", ""),
            "stages": inv.get("stage_focus", []),
            "sectors": inv.get("sector_focus", []),
            "last_active": inv.get("last_active", ""),
            "url": f"/investors/{inv['slug']}.html",
        }
    (OUTPUT_DIR / "investor-lookup.json").write_text(json.dumps(investor_lookup_data))

    # Generate startup-investor map for comparable companies finder
    startup_investor_map = build_startup_investor_map(startups, investor_lookup, firm_lookup)
    (OUTPUT_DIR / "startup-investor-map.json").write_text(json.dumps(startup_investor_map))

    # Generate investor graph for "Paths to" feature
    investor_graph = build_investor_graph(investors, firms, startups, clusters_data)
    (OUTPUT_DIR / "investor-graph.json").write_text(json.dumps(investor_graph))

    # Generate rounds feed JSON and render rounds page
    rounds_feed = build_rounds_feed(startups)
    (OUTPUT_DIR / "rounds-feed.json").write_text(json.dumps(rounds_feed, indent=2))
    rounds_tmpl_path = TEMPLATES_DIR / "rounds.html"
    if rounds_tmpl_path.exists():
        rounds_template = env.get_template("rounds.html")
        html = rounds_template.render()
        (OUTPUT_DIR / "rounds.html").write_text(html)

    # Render enrich page
    enrich_tmpl_path = TEMPLATES_DIR / "enrich.html"
    if enrich_tmpl_path.exists():
        enrich_template = env.get_template("enrich.html")
        html = enrich_template.render(
            investor_count=len(investors),
            firm_count=len(firms),
        )
        (OUTPUT_DIR / "enrich.html").write_text(html)

    # Render find investors page
    find_tmpl_path = TEMPLATES_DIR / "find.html"
    if find_tmpl_path.exists():
        from collections import Counter
        find_sector_counts = Counter()
        for inv in investors:
            for s in (inv.get("sector_focus") or []):
                find_sector_counts[s] += 1
        top_sectors_find = [s for s, _ in find_sector_counts.most_common(25)]

        find_template = env.get_template("find.html")
        html = find_template.render(
            investor_count=len(investors),
            top_sectors=top_sectors_find,
        )
        (OUTPUT_DIR / "find.html").write_text(html)

    # Render discover (founder tools routing) page
    discover_tmpl_path = TEMPLATES_DIR / "discover.html"
    if discover_tmpl_path.exists():
        discover_template = env.get_template("discover.html")
        html = discover_template.render(
            investor_count=len(investors),
        )
        (OUTPUT_DIR / "discover.html").write_text(html)

    # Render comparables page
    comparables_tmpl_path = TEMPLATES_DIR / "comparables.html"
    if comparables_tmpl_path.exists():
        comparables_template = env.get_template("comparables.html")
        html = comparables_template.render()
        (OUTPUT_DIR / "comparables.html").write_text(html)

    # Render agents page
    agents_tmpl_path = TEMPLATES_DIR / "agents.html"
    if agents_tmpl_path.exists():
        agents_template = env.get_template("agents.html")
        html = agents_template.render(
            investor_count=len(investors),
            firm_count=len(firms),
            startup_count=len(startups),
        )
        (OUTPUT_DIR / "agents.html").write_text(html)

    # Render homepage
    index_template = env.get_template("index.html")
    html = index_template.render(
        investor_count=len(investors),
        firm_count=len(firms),
        startup_count=len(startups),
        stages=stages,
        sectors=sectors,
    )
    (OUTPUT_DIR / "index.html").write_text(html)

    # Generate cluster data JSON
    if clusters_data:
        (OUTPUT_DIR / "cluster-data.json").write_text(json.dumps(clusters_data))

    # Copy static assets
    if STATIC_DIR.exists():
        static_out = OUTPUT_DIR / "static"
        shutil.copytree(STATIC_DIR, static_out)

    # Copy llms.txt to site root (convention for AI agents)
    llms_path = STATIC_DIR / "llms.txt"
    if llms_path.exists():
        shutil.copy2(llms_path, OUTPUT_DIR / "llms.txt")

    # Copy CNAME for custom domain
    cname_path = ROOT / "CNAME"
    if cname_path.exists():
        shutil.copy2(cname_path, OUTPUT_DIR / "CNAME")

    print(f"Built {len(investors)} investor pages, {len(firms)} firm pages, {len(startups)} startup pages")
    print(f"Generated {len(stages)} stage listings, {len(sectors)} sector listings")
    print(f"Search index: {len(search_index)} entries")
    print(f"Rounds feed: {len(rounds_feed)} rounds")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    build()
