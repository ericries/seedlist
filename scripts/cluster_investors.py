#!/usr/bin/env python3
"""Cluster investors by similarity for the Seedlist directory."""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import frontmatter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INVESTORS_DIR = PROJECT_ROOT / "data" / "investors"
SITE_DIR = PROJECT_ROOT / "_site"
DATA_OUT = PROJECT_ROOT / "data" / "clusters.json"
SITE_OUT = SITE_DIR / "cluster-data.json"

# Weights for similarity components
W_STAGE = 0.15
W_SECTOR = 0.30
W_PORTFOLIO = 0.40
W_LOCATION = 0.10
W_FIRM = 0.05

# Sector normalisation aliases
SECTOR_ALIASES = {
    "ai": "ai",
    "ai-ml": "ai",
    "artificial-intelligence": "ai",
    "machine-learning": "ai",
    "ml": "ai",
    "saas": "saas",
    "enterprise-saas": "saas",
    "enterprise": "saas",
    "dev-tools": "developer-tools",
    "devtools": "developer-tools",
    "crypto": "crypto-web3",
    "web3": "crypto-web3",
    "blockchain": "crypto-web3",
    "defi": "crypto-web3",
    "ecommerce": "e-commerce",
    "health": "healthcare",
    "healthtech": "healthcare",
    "health-tech": "healthcare",
    "bio": "biotech",
    "life-sciences": "biotech",
    "infra": "infrastructure",
    "data-infrastructure": "infrastructure",
    "cloud-infrastructure": "infrastructure",
    "cloud": "infrastructure",
    "consumer": "consumer-internet",
    "consumer-tech": "consumer-internet",
    "social": "consumer-internet",
    "social-media": "consumer-internet",
    "marketplace": "marketplaces",
    "marketplace-platforms": "marketplaces",
    "defense": "defense-govtech",
    "govtech": "defense-govtech",
    "defence": "defense-govtech",
    "robotics": "robotics-hardware",
    "hardware": "robotics-hardware",
}

# Location region mapping
LOCATION_REGIONS = {
    "sf bay area": [
        "san francisco", "menlo park", "palo alto", "mountain view",
        "sunnyvale", "redwood city", "cupertino", "santa clara",
        "san mateo", "berkeley", "oakland", "south san francisco",
        "san jose", "woodside", "atherton", "portola valley",
        "half moon bay", "los altos", "saratoga", "mill valley",
        "tiburon", "burlingame", "foster city", "fremont",
        "pleasanton", "walnut creek", "palo alto, ca",
    ],
    "nyc": ["new york", "brooklyn", "manhattan"],
    "la": ["los angeles", "santa monica", "venice", "culver city", "beverly hills", "pasadena", "west hollywood"],
    "boston": ["boston", "cambridge, ma", "somerville, ma"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalise_sector(s: str) -> str:
    """Normalise a sector string to a canonical form."""
    s = s.strip().lower()
    return SECTOR_ALIASES.get(s, s)


def location_to_region(loc: str | None) -> str:
    """Map a location string to a broad region."""
    if not loc:
        return "Other"
    loc_lower = loc.lower()
    for region, keywords in LOCATION_REGIONS.items():
        for kw in keywords:
            if kw in loc_lower:
                return region.upper() if region in ("nyc", "la") else region.title()
    # Heuristic for US vs international
    us_states = [
        ", ca", ", ny", ", tx", ", wa", ", ma", ", il", ", co", ", fl",
        ", ga", ", pa", ", ct", ", nj", ", va", ", md", ", or", ", ut",
        ", az", ", nc", ", oh", ", mn", ", mi", ", tn", ", dc",
        "california", "texas", "washington", "illinois", "colorado",
        "florida", "georgia", "connecticut", "virginia", "maryland",
        "oregon", "utah", "arizona", "united states",
    ]
    europe_keywords = [
        "london", "berlin", "paris", "amsterdam", "stockholm",
        "munich", "zurich", "dublin", "lisbon", "barcelona",
        "madrid", "uk", "england", "france", "germany", "switzerland",
        "sweden", "netherlands", "ireland", "europe", "israel", "tel aviv",
    ]
    asia_keywords = [
        "singapore", "hong kong", "tokyo", "beijing", "shanghai",
        "bangalore", "mumbai", "delhi", "india", "china", "japan",
        "korea", "seoul", "asia", "taiwan",
    ]
    for kw in europe_keywords:
        if kw in loc_lower:
            return "Europe"
    for kw in asia_keywords:
        if kw in loc_lower:
            return "Asia"
    for kw in us_states:
        if kw in loc_lower:
            return "Other US"
    return "Other"


def strip_markdown_link(text: str) -> str:
    """Strip markdown link syntax: [Name](url) -> Name."""
    return re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)


def parse_portfolio(content: str) -> list[str]:
    """Extract company names from the ## Portfolio section's markdown table."""
    companies = []
    in_portfolio = False
    past_header = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## Portfolio"):
            in_portfolio = True
            continue
        if in_portfolio and stripped.startswith("## "):
            break
        if not in_portfolio:
            continue
        # Skip table header and separator rows
        if stripped.startswith("|") and ("Company" in stripped or "---" in stripped):
            past_header = True
            continue
        if not past_header:
            continue
        if stripped.startswith("|"):
            cols = [c.strip() for c in stripped.split("|")]
            # cols[0] is empty (before first |), cols[1] is company
            if len(cols) >= 2:
                raw = cols[1]
                name = strip_markdown_link(raw).strip()
                name_lower = name.lower()
                if name_lower and name_lower not in ("~unknown", "unknown", "", "--", "—"):
                    companies.append(name_lower)
    return companies


def jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def load_investors() -> list[dict]:
    """Load all published investor profiles."""
    investors = []
    for path in sorted(INVESTORS_DIR.glob("*.md")):
        try:
            post = frontmatter.load(str(path))
        except Exception as e:
            print(f"  Warning: could not parse {path.name}: {e}")
            continue

        meta = post.metadata
        if meta.get("status") != "published":
            continue

        stages = set(meta.get("stage_focus", []) or [])
        sectors = {normalise_sector(s) for s in (meta.get("sector_focus", []) or [])}
        location = meta.get("location", "")
        region = location_to_region(location)
        firm = meta.get("firm", "") or ""
        slug = meta.get("slug", path.stem)
        name = meta.get("name", slug)
        portfolio = parse_portfolio(post.content)

        investors.append({
            "slug": slug,
            "name": name,
            "firm": firm,
            "location": location or "",
            "region": region,
            "stages": stages,
            "sectors": sectors,
            "portfolio": set(portfolio),
            "portfolio_list": portfolio,
        })
    return investors


def build_similarity_matrix(investors: list[dict]) -> list[list[float]]:
    """Build pairwise similarity matrix."""
    n = len(investors)
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        sim[i][i] = 1.0
        for j in range(i + 1, n):
            a, b = investors[i], investors[j]
            s_stage = jaccard(a["stages"], b["stages"])
            s_sector = jaccard(a["sectors"], b["sectors"])
            s_portfolio = jaccard(a["portfolio"], b["portfolio"])
            s_location = 1.0 if a["region"] == b["region"] else 0.0
            s_firm = 1.0 if (a["firm"] and a["firm"] == b["firm"]) else 0.0
            similarity = (
                W_STAGE * s_stage
                + W_SECTOR * s_sector
                + W_PORTFOLIO * s_portfolio
                + W_LOCATION * s_location
                + W_FIRM * s_firm
            )
            sim[i][j] = similarity
            sim[j][i] = similarity
    return sim


def cluster_investors_scipy(dist_matrix, n_investors: int, target_clusters: int = 12):
    """Cluster using scipy hierarchical clustering."""
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    # Convert full distance matrix to condensed form
    condensed = squareform(dist_matrix)
    Z = linkage(condensed, method="ward")

    # Binary search for the right cut height to get ~target_clusters
    best_labels = None
    best_diff = float("inf")

    lo, hi = 0.0, Z[-1, 2]
    for _ in range(100):
        mid = (lo + hi) / 2
        labels = fcluster(Z, t=mid, criterion="distance")
        n_clusters = len(set(labels))
        diff = abs(n_clusters - target_clusters)
        if diff < best_diff or (diff == best_diff and n_clusters >= target_clusters):
            best_diff = diff
            best_labels = labels.copy()
        if n_clusters > target_clusters:
            lo = mid
        elif n_clusters < target_clusters:
            hi = mid
        else:
            break

    return best_labels


def compute_cluster_summaries(investors: list[dict], labels, sim_matrix) -> dict:
    """Compute cluster summaries and output data."""
    cluster_map = defaultdict(list)
    for idx, label in enumerate(labels):
        cluster_map[int(label)].append(idx)

    # Renumber clusters 0..N-1
    clusters_out = []
    investor_cluster_map = {}
    old_to_new = {}
    for new_id, (old_id, member_indices) in enumerate(sorted(cluster_map.items())):
        old_to_new[old_id] = new_id

        # Collect stats
        all_sectors = []
        all_stages = []
        all_locations = []
        all_portfolio = []
        members = []
        for idx in member_indices:
            inv = investors[idx]
            all_sectors.extend(inv["sectors"])
            all_stages.extend(inv["stages"])
            all_locations.append(inv["region"])
            all_portfolio.extend(inv["portfolio_list"])
            members.append({
                "slug": inv["slug"],
                "name": inv["name"],
                "firm": inv["firm"],
            })
            investor_cluster_map[inv["slug"]] = new_id

        top_sectors = [s for s, _ in Counter(all_sectors).most_common(5)]
        top_stages = [s for s, _ in Counter(all_stages).most_common(3)]
        top_locations = [loc for loc, _ in Counter(all_locations).most_common(3)]

        # Shared portfolio: companies in 3+ members' portfolios
        portfolio_counter = Counter(all_portfolio)
        shared = [company.title() for company, count in portfolio_counter.most_common()
                  if count >= 3]

        # If few shared at threshold 3, try threshold 2
        if len(shared) < 3 and len(member_indices) >= 5:
            shared = [company.title() for company, count in portfolio_counter.most_common(10)
                      if count >= 2]

        # Build summary sentence
        stage_str = ", ".join(top_stages[:2]) if top_stages else "multi-stage"
        sector_str = ", ".join(top_sectors[:3]) if top_sectors else "diversified"
        location_str = top_locations[0] if top_locations else "various locations"
        portfolio_str = ""
        if shared[:3]:
            portfolio_str = f", with shared investments in {', '.join(shared[:3])}"
        summary = (
            f"{stage_str.replace('-', ' ').title()}-focused {sector_str} investors "
            f"primarily based in {location_str}{portfolio_str}"
        )

        clusters_out.append({
            "id": new_id,
            "name": "",
            "tagline": "",
            "size": len(member_indices),
            "top_sectors": top_sectors,
            "top_stages": top_stages,
            "top_locations": top_locations,
            "shared_portfolio": shared[:15],
            "members": sorted(members, key=lambda m: m["name"]),
            "summary": summary,
        })

    return {
        "clusters": clusters_out,
        "investor_clusters": investor_cluster_map,
    }


def compute_similar_investors(investors: list[dict], sim_matrix, k: int = 5) -> dict:
    """For each investor, find the k most similar investors."""
    similar = {}
    for i, inv in enumerate(investors):
        scored = []
        for j, other in enumerate(investors):
            if i == j:
                continue
            scored.append((sim_matrix[i][j], other["slug"]))
        scored.sort(key=lambda x: -x[0])
        similar[inv["slug"]] = [slug for _, slug in scored[:k]]
    return similar


def main():
    print("Loading published investor profiles...")
    investors = load_investors()
    print(f"  Found {len(investors)} published investors")

    if len(investors) < 2:
        print("Not enough investors to cluster. Exiting.")
        sys.exit(1)

    print("Building similarity matrix...")
    sim_matrix = build_similarity_matrix(investors)

    # Convert to distance matrix
    n = len(investors)
    dist_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            dist_matrix[i][j] = max(0.0, 1.0 - sim_matrix[i][j])

    # Determine target cluster count (aim for 12-15, adjust for small sets)
    target = max(2, min(15, len(investors) // 15))
    print(f"  Target clusters: {target}")

    print("Running hierarchical clustering (Ward's method)...")
    try:
        import numpy as np
        dist_np = np.array(dist_matrix)
        labels = cluster_investors_scipy(dist_np, n, target_clusters=target)
    except ImportError:
        print("  scipy/numpy not available — cannot cluster.")
        sys.exit(1)

    n_clusters = len(set(labels))
    print(f"  Produced {n_clusters} clusters")

    # Report cluster sizes
    cluster_sizes = Counter(int(l) for l in labels)
    for cid, size in sorted(cluster_sizes.items()):
        print(f"    Cluster {cid}: {size} investors")

    print("Computing cluster summaries...")
    result = compute_cluster_summaries(investors, labels, sim_matrix)

    print("Computing per-investor similarity rankings...")
    similar = compute_similar_investors(investors, sim_matrix, k=5)
    result["similar_investors"] = similar

    # Write output files
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    for out_path in (DATA_OUT, SITE_OUT):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"  Wrote {out_path}")

    # Summary
    print(f"\nDone. {n_clusters} clusters from {len(investors)} investors.")
    for cluster in result["clusters"]:
        print(f"  [{cluster['id']}] ({cluster['size']} members) {cluster['summary']}")


if __name__ == "__main__":
    main()
