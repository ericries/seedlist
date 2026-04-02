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
]

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

    # Scrape all feeds
    new_count = 0
    for feed_config in FEEDS:
        candidates = scrape_feed(feed_config)
        for candidate in candidates:
            if candidate["url"] in existing_urls:
                continue
            data["pending_rounds"].append(candidate)
            existing_urls.add(candidate["url"])
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
