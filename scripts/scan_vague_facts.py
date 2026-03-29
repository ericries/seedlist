#!/usr/bin/env python3
"""Scan all published profiles for vague facts and write a prioritized queue.

Outputs data/vague-facts-queue.yaml with facts to investigate, sorted by priority.
Priority: "Unknown" round types > approximate amounts > year-only dates on recent rounds.
"""

import re
import sys
from pathlib import Path

import frontmatter
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
QUEUE_PATH = DATA / "vague-facts-queue.yaml"


def scan_profiles():
    facts = []

    for d in ["investors", "firms", "startups"]:
        for f in sorted((DATA / d).glob("*.md")):
            try:
                post = frontmatter.load(str(f))
            except Exception:
                continue
            if post.metadata.get("status") != "published":
                continue

            slug = f.stem
            name = post.metadata.get("name", slug)
            profile_type = d.rstrip("s")  # investor, firm, startup
            content = post.content or ""

            section = ""
            for line in content.split("\n"):
                if line.startswith("## "):
                    section = line[3:].strip()

                if "|" not in line or section not in ("Portfolio", "Funding History"):
                    continue

                parts = [p.strip() for p in line.split("|") if p.strip()]
                if not parts or parts[0].startswith("---"):
                    continue
                # Skip header rows
                if any(h in parts[0].lower() for h in ("company", "date", "round")):
                    continue

                # Detect issues
                for i, cell in enumerate(parts):
                    cell_clean = cell.lower().strip()
                    # Strip footnote refs for analysis
                    cell_clean = re.sub(r'\[\^\d+\]', '', cell_clean).strip()

                    if cell_clean in ("unknown", "undisclosed", "n/a", "--", "—", "?", ""):
                        # High priority: explicit unknown
                        company = parts[0] if parts else "?"
                        company = re.sub(r'\[\^\d+\]', '', company).strip()
                        facts.append({
                            "profile": f"{d}/{slug}",
                            "profile_name": name,
                            "company": company,
                            "section": section,
                            "column": i,
                            "value": cell.strip(),
                            "line": line.strip()[:120],
                            "priority": "high",
                            "type": "unknown_value",
                            "status": "pending",
                        })

                    elif re.match(r'^~?\d{4}$', cell_clean):
                        # Lower priority: year-only date (very common)
                        company = parts[0] if parts else "?"
                        company = re.sub(r'\[\^\d+\]', '', company).strip()
                        year = int(cell_clean.replace("~", ""))
                        # Prioritize recent years (more likely to find exact date)
                        pri = "normal" if year >= 2023 else "low"
                        facts.append({
                            "profile": f"{d}/{slug}",
                            "profile_name": name,
                            "company": company,
                            "section": section,
                            "column": i,
                            "value": cell.strip(),
                            "line": line.strip()[:120],
                            "priority": pri,
                            "type": "year_only_date",
                            "status": "pending",
                        })

    return facts


def main():
    print("Scanning profiles for vague facts...")
    facts = scan_profiles()

    # Deduplicate: same profile + company + type
    seen = set()
    deduped = []
    for f in facts:
        key = (f["profile"], f["company"], f["type"])
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    # Sort: high priority first, then normal, then low
    priority_order = {"high": 0, "normal": 1, "low": 2}
    deduped.sort(key=lambda x: (priority_order.get(x["priority"], 9), x["profile"]))

    high = sum(1 for f in deduped if f["priority"] == "high")
    normal = sum(1 for f in deduped if f["priority"] == "normal")
    low = sum(1 for f in deduped if f["priority"] == "low")

    print(f"Found {len(deduped)} vague facts: {high} high, {normal} normal, {low} low priority")

    # Write queue
    with open(QUEUE_PATH, "w") as fh:
        yaml.dump({"vague_facts": deduped}, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"Wrote {QUEUE_PATH}")


if __name__ == "__main__":
    main()
