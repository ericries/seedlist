#!/usr/bin/env python3
"""
scrape_rounds.py — Scrape funding round announcements from RSS feeds.

Fetches TechCrunch, Crunchbase News, and AlleyWatch RSS feeds, filters for
funding-related articles, parses company/amount/round from titles, and writes
candidates to data/pending-rounds.yaml.

No external dependencies beyond stdlib + pyyaml.
"""

import os
import re
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# pyyaml — available in CI via pip install, locally via venv
import yaml

ROOT = Path(__file__).resolve().parent.parent
PENDING_PATH = ROOT / "data" / "pending-rounds.yaml"

MAX_ENTRIES = 100  # keep last N entries, rotate old ones out

# RSS feeds to scrape
FEEDS = [
    # Tier 1: Wire services (PRIMARY sources — company press releases)
    {
        "name": "prnewswire",
        "url": "https://www.prnewswire.com/rss/financial-services-latest-news/venture-capital-list/rss-702702.xml",
        "title_filters": ["raises", "funding", "secures", "closes", "series", "seed"],
    },
    {
        "name": "businesswire",
        "url": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJhkQ%3D",
        "title_filters": ["raises", "funding", "secures", "closes", "series", "seed"],
    },
    {
        "name": "globenewswire",
        "url": "https://www.globenewswire.com/RssFeed/subjectcode/58-Funding%20Activities/feedTitle/GlobeNewsWire%20-%20Funding%20Activities",
        "title_filters": ["raises", "funding", "secures", "closes", "series", "seed"],
    },
    # Tier 2: Aggregators with structured titles
    {
        "name": "finsmes",
        "url": "https://www.finsmes.com/feed",
        "title_filters": ["raises", "funding", "series", "seed"],
    },
    {
        "name": "vcnewsdaily",
        "url": "https://vcnewsdaily.com/feed/",
        "title_filters": ["raises", "funding", "venture", "series", "seed"],
    },
    # Tier 3: Tech press
    {
        "name": "techcrunch",
        "url": "https://techcrunch.com/feed/",
        "title_filters": ["raises", "funding", "series", "seed"],
    },
    {
        "name": "crunchbase",
        "url": "https://news.crunchbase.com/feed/",
        "title_filters": ["raises", "funding", "series", "seed"],
    },
    {
        "name": "alleywatch",
        "url": "https://alleywatch.com/feed/",
        "title_filters": ["funding report"],
    },
    # Tier 4: Regional
    {
        "name": "eu-startups",
        "url": "https://www.eu-startups.com/feed/",
        "title_filters": ["raises", "funding", "secures", "series", "seed"],
    },
]

# Axios Pro Rata — not RSS, scraped as HTML (latest edition always free)
AXIOS_PRO_RATA_URL = "https://www.axios.com/newsletters/axios-pro-rata"

# Regex patterns to extract amount and round type from article titles
AMOUNT_RE = re.compile(
    r"\$\s*(\d+(?:\.\d+)?)\s*(million|mil|m|billion|bil|b)\b", re.IGNORECASE
)
AMOUNT_SHORT_RE = re.compile(r"\$(\d+(?:\.\d+)?)(M|B|K)\b")
ROUND_RE = re.compile(
    r"\b(pre[- ]?seed|seed|series\s+[a-f](?:\d)?|series\s+[a-f]\d?|bridge|convertible note)\b",
    re.IGNORECASE,
)
# Try to extract company name: text before "raises" or "secures" or "closes"
COMPANY_RE = re.compile(
    r"^(.+?)\s+(?:raises|secures|closes|lands|nabs|gets|announces|bags)\s",
    re.IGNORECASE,
)


def fetch_feed(url, timeout=30):
    """Fetch an RSS feed and return parsed XML root. Returns None on error."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Seedlist-Scraper/1.0 (https://seedlist.com)",
                "Accept": "application/rss+xml, application/xml, text/xml",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        return ET.fromstring(data)
    except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError, OSError) as e:
        print(f"  Warning: failed to fetch {url}: {e}", file=sys.stderr)
        return None


def matches_filters(title, filters):
    """Check if title contains any of the filter keywords (case-insensitive)."""
    title_lower = title.lower()
    return any(f.lower() in title_lower for f in filters)


def parse_amount(title):
    """Try to extract a dollar amount from the title."""
    # Try short form first: $30M, $1.5B
    m = AMOUNT_SHORT_RE.search(title)
    if m:
        num, suffix = m.group(1), m.group(2).upper()
        return f"${num}{suffix}"

    # Try long form: $30 million, $1.5 billion
    m = AMOUNT_RE.search(title)
    if m:
        num, unit = m.group(1), m.group(2).lower()
        if unit in ("billion", "bil", "b"):
            return f"${num}B"
        else:
            return f"${num}M"

    return None


def parse_round(title):
    """Try to extract round type from the title."""
    m = ROUND_RE.search(title)
    if m:
        return m.group(1).title()
    return None


def parse_company(title):
    """Try to extract company name from the title."""
    m = COMPANY_RE.match(title)
    if m:
        company = m.group(1).strip()
        # Clean up common prefixes
        for prefix in ["Exclusive:", "Breaking:", "Report:"]:
            if company.startswith(prefix):
                company = company[len(prefix):].strip()
        return company if company else None
    return None


def parse_date(date_str):
    """Parse RSS date string to YYYY-MM-DD."""
    # RSS dates are typically RFC 822: "Wed, 01 Apr 2026 12:00:00 +0000"
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Fallback: today's date
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def scrape_feed(feed_config):
    """Scrape a single RSS feed and return list of round candidates."""
    name = feed_config["name"]
    url = feed_config["url"]
    filters = feed_config["title_filters"]

    print(f"Fetching {name}: {url}")
    root = fetch_feed(url)
    if root is None:
        return []

    items = []
    # Handle both RSS 2.0 (<channel><item>) and Atom (<entry>) formats
    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")

        if title_el is None or link_el is None:
            continue

        title = title_el.text or ""
        link = link_el.text or ""

        if not matches_filters(title, filters):
            continue

        date_found = parse_date(pubdate_el.text) if pubdate_el is not None and pubdate_el.text else datetime.now(timezone.utc).strftime("%Y-%m-%d")

        entry = {
            "title": title.strip(),
            "url": link.strip(),
            "source": name,
            "date_found": date_found,
            "parsed_company": parse_company(title),
            "parsed_amount": parse_amount(title),
            "parsed_round": parse_round(title),
            "status": "pending",
        }
        items.append(entry)

    # Also check Atom format
    for ns in ["", "{http://www.w3.org/2005/Atom}"]:
        for entry_el in root.iter(f"{ns}entry"):
            title_el = entry_el.find(f"{ns}title")
            link_el = entry_el.find(f"{ns}link")
            updated_el = entry_el.find(f"{ns}updated") or entry_el.find(f"{ns}published")

            if title_el is None or link_el is None:
                continue

            title = title_el.text or ""
            # Atom links use href attribute
            link = link_el.get("href", link_el.text or "")

            if not matches_filters(title, filters):
                continue

            date_found = parse_date(updated_el.text) if updated_el is not None and updated_el.text else datetime.now(timezone.utc).strftime("%Y-%m-%d")

            entry = {
                "title": title.strip(),
                "url": link.strip(),
                "source": name,
                "date_found": date_found,
                "parsed_company": parse_company(title),
                "parsed_amount": parse_amount(title),
                "parsed_round": parse_round(title),
                "status": "pending",
            }
            items.append(entry)

    print(f"  Found {len(items)} funding-related articles from {name}")
    return items


def scrape_axios_pro_rata():
    """Scrape the latest Axios Pro Rata newsletter for VC deals.

    The latest edition is always available without paywall at a fixed URL.
    We fetch the HTML and extract deal mentions using regex patterns.
    """
    print(f"Fetching Axios Pro Rata: {AXIOS_PRO_RATA_URL}")
    try:
        req = urllib.request.Request(
            AXIOS_PRO_RATA_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print(f"  Warning: failed to fetch Axios Pro Rata: {e}", file=sys.stderr)
        return []

    items = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Look for deal patterns in the HTML text
    # Strip HTML tags for text analysis
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    # Pattern: "Company raised $XM in Series Y funding" or "Company, a ..., raised $XM"
    deal_pattern = re.compile(
        r"([A-Z][A-Za-z0-9 &\-\.]+?)\s*(?:,\s*(?:a|an|the)\s+[^,]+?,\s+)?"
        r"(?:raised|closed|secured|nabbed)\s+"
        r"\$\s*(\d+(?:\.\d+)?)\s*(million|mil|m|billion|bil|b)\b"
        r"(?:\s+in\s+(\w[\w\s]*?)(?:\s+funding|\s+round|\s+financing))?"
        , re.IGNORECASE
    )

    for match in deal_pattern.finditer(text):
        company = match.group(1).strip()
        num = match.group(2)
        unit = match.group(3).lower()
        round_type = match.group(4)

        # Skip common false positives
        if company.lower() in ("the company", "it", "they", "which", "who", "that"):
            continue
        if len(company) < 2 or len(company) > 60:
            continue

        amount_suffix = "B" if unit in ("billion", "bil", "b") else "M"
        amount = f"${num}{amount_suffix}"

        entry = {
            "title": f"{company} raised {amount}" + (f" {round_type}" if round_type else ""),
            "url": AXIOS_PRO_RATA_URL,
            "source": "axios-pro-rata",
            "date_found": today,
            "parsed_company": company,
            "parsed_amount": amount,
            "parsed_round": round_type.strip().title() if round_type else None,
            "status": "pending",
        }
        items.append(entry)

    print(f"  Found {len(items)} deal mentions from Axios Pro Rata")
    return items


def load_pending():
    """Load existing pending rounds file."""
    if not PENDING_PATH.exists():
        return {"pending_rounds": []}
    with open(PENDING_PATH) as f:
        data = yaml.safe_load(f) or {}
    if "pending_rounds" not in data:
        data["pending_rounds"] = []
    return data


def save_pending(data):
    """Save pending rounds file."""
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PENDING_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def main():
    print(f"Seedlist Round Scraper — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # Load existing data
    data = load_pending()
    existing_urls = {entry["url"] for entry in data["pending_rounds"]}
    initial_count = len(data["pending_rounds"])

    # Scrape all RSS feeds
    new_count = 0
    for feed_config in FEEDS:
        candidates = scrape_feed(feed_config)
        for candidate in candidates:
            if candidate["url"] in existing_urls:
                continue
            data["pending_rounds"].append(candidate)
            existing_urls.add(candidate["url"])
            new_count += 1

    # Scrape Axios Pro Rata (HTML, not RSS)
    axios_candidates = scrape_axios_pro_rata()
    for candidate in axios_candidates:
        # Dedup by company name (Axios URL is always the same)
        company = (candidate.get("parsed_company") or "").lower()
        existing_companies = {
            (e.get("parsed_company") or "").lower()
            for e in data["pending_rounds"]
            if e.get("source") == "axios-pro-rata"
        }
        if company and company in existing_companies:
            continue
        if candidate["url"] not in existing_urls or candidate.get("source") == "axios-pro-rata":
            data["pending_rounds"].append(candidate)
            new_count += 1

    # Sort by date (newest first)
    data["pending_rounds"].sort(key=lambda x: x.get("date_found", ""), reverse=True)

    # Rotate: keep only the last MAX_ENTRIES
    if len(data["pending_rounds"]) > MAX_ENTRIES:
        data["pending_rounds"] = data["pending_rounds"][:MAX_ENTRIES]

    # Save
    save_pending(data)

    print()
    print(f"New entries added: {new_count}")
    print(f"Total entries: {len(data['pending_rounds'])} (max {MAX_ENTRIES})")
    pending = sum(1 for e in data["pending_rounds"] if e.get("status") == "pending")
    print(f"Pending review: {pending}")


if __name__ == "__main__":
    main()
