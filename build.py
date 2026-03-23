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
            # Strip HTML tags and get first 200 chars
            text = re.sub(r'<[^>]+>', ' ', m.group(1))
            text = re.sub(r'\s+', ' ', text).strip()
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
            "sector_focus": p.get("sector_focus", []),
            "check_size": p.get("check_size", ""),
            "last_active": last_active,
            "status": p.get("status", ""),
            "thesis_summary": thesis_summary,
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


def build():
    """Build the static site."""
    # Clean output
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # Set up Jinja2
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

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

    # Build cluster lookup for investor pages
    similar_investors_map = clusters_data.get("similar_investors", {})
    investor_clusters_map = clusters_data.get("investor_clusters", {})
    clusters_list = clusters_data.get("clusters", [])
    cluster_by_id = {c["id"]: c for c in clusters_list}

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

        html = investor_template.render(
            profile=profile,
            similar_investors=similar,
            investor_cluster=inv_cluster,
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
    if clusters_list:
        clusters_template = env.get_template("clusters.html")
        html = clusters_template.render(
            clusters=clusters_list,
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
    (OUTPUT_DIR / "enrichment-index.json").write_text(json.dumps(enrichment_index))

    # Render enrich page
    enrich_tmpl_path = TEMPLATES_DIR / "enrich.html"
    if enrich_tmpl_path.exists():
        enrich_template = env.get_template("enrich.html")
        html = enrich_template.render(
            investor_count=len(investors),
            firm_count=len(firms),
        )
        (OUTPUT_DIR / "enrich.html").write_text(html)

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

    # Copy static assets
    if STATIC_DIR.exists():
        static_out = OUTPUT_DIR / "static"
        shutil.copytree(STATIC_DIR, static_out)

    # Copy CNAME for custom domain
    cname_path = ROOT / "CNAME"
    if cname_path.exists():
        shutil.copy2(cname_path, OUTPUT_DIR / "CNAME")

    print(f"Built {len(investors)} investor pages, {len(firms)} firm pages, {len(startups)} startup pages")
    print(f"Generated {len(stages)} stage listings, {len(sectors)} sector listings")
    print(f"Search index: {len(search_index)} entries")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    build()
