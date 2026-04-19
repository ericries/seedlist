#!/usr/bin/env python3
"""Process GitHub Issues for the Seedlist project.

SECURITY: This script processes user-submitted GitHub Issues. User text is NEVER
passed to an LLM. All processing is mechanical parsing, validation, and structured
data writes. All gh CLI calls use list-based arguments, never shell=True with user text.
"""

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import frontmatter
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
QUEUE_PATH = DATA / "queue.yaml"

TODAY_STR = date.today().strftime("%Y-%m-%d")

ALLOWED_DOMAINS = {
    "techcrunch.com", "crunchbase.com", "pitchbook.com", "linkedin.com",
    "forbes.com", "bloomberg.com", "wsj.com", "twitter.com", "x.com",
    "nytimes.com", "medium.com", "substack.com", "reuters.com",
    "businessinsider.com", "ft.com", "theinformation.com",
    "venturebeat.com", "sifted.eu", "axios.com", "cnbc.com",
    "youtube.com", "podcasts.apple.com", "spotify.com",
}


def _load_firm_domains():
    """Load allowed domains dynamically from existing firm profile websites."""
    domains = set()
    firms_dir = DATA / "firms"
    if not firms_dir.exists():
        return domains
    for path in firms_dir.glob("*.md"):
        try:
            post = frontmatter.load(str(path))
            website = post.metadata.get("website", "")
            if website:
                domain = get_base_domain(website)
                if domain:
                    domains.add(domain)
        except Exception:
            continue
    return domains


def get_base_domain(url):
    """Extract domain from URL, stripping www. prefix."""
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        domain = domain.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def get_allowed_domains():
    """Return the full set of allowed domains (static + firm websites)."""
    return ALLOWED_DOMAINS | _load_firm_domains()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def run_gh(args):
    """Run a gh CLI command and return stdout. args is a list of strings.

    SECURITY: args must be a list — never interpolate user text into a shell string.
    """
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def close_issue(number, comment):
    """Close a GitHub issue with a comment.

    SECURITY: number is an int, comment is script-generated (not raw user text).
    """
    run_gh(["issue", "close", str(number), "--comment", comment])


def label_issue(number, label):
    """Add a label to a GitHub issue.

    SECURITY: number is an int, label is a hardcoded string.
    """
    run_gh(["issue", "edit", str(number), "--add-label", label])


def find_profile(slug):
    """Check all three data dirs for a profile, return Path or None."""
    for subdir in ("investors", "firms", "startups"):
        path = DATA / subdir / f"{slug}.md"
        if path.exists():
            return path
    return None


def looks_like_name(name):
    """Validation heuristic: does this string look like a person's name?"""
    if len(name) < 3:
        return False
    if len(name.split()) < 2:
        return False
    if "@" in name:
        return False
    if name.replace(" ", "").isdigit():
        return False
    if re.search(r'[<>;\{\}|\\]', name):
        return False
    return True


def load_queue():
    """Load queue.yaml and return the parsed dict."""
    if not QUEUE_PATH.exists():
        return {"queue": []}
    with open(QUEUE_PATH, "r") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {"queue": []}
    return data


def save_queue(data):
    """Write queue data back to queue.yaml."""
    with open(QUEUE_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Source submission processing
# ---------------------------------------------------------------------------

def process_source_issues():
    """Process issues labeled 'source-submission'."""
    try:
        raw = run_gh([
            "issue", "list",
            "--label", "source-submission",
            "--state", "open",
            "--json", "number,title,body,labels",
            "--limit", "20",
        ])
    except subprocess.CalledProcessError as e:
        print(f"  Failed to list source-submission issues: {e}")
        return

    if not raw:
        print("  No source-submission issues found.")
        return

    issues = json.loads(raw)

    for issue in issues:
        number = issue["number"]
        body = issue.get("body", "") or ""
        labels = [l.get("name", "") for l in issue.get("labels", [])]
        print(f"  Processing issue #{number}...")

        # Skip issues already flagged for review (prevents duplicate comments)
        if "needs-review" in labels:
            print(f"    Skipping #{number}: already flagged needs-review")
            continue

        # Parse fields from body
        slug_match = re.search(r"^slug:\s*(.+)$", body, re.MULTILINE)
        type_match = re.search(r"^type:\s*(.+)$", body, re.MULTILINE)
        url_match = re.search(r"^url:\s*(.+)$", body, re.MULTILINE)

        if not slug_match or not url_match:
            print(f"    Skipping #{number}: missing slug or url in body")
            continue

        slug = slug_match.group(1).strip()
        profile_type = type_match.group(1).strip() if type_match else ""
        url = url_match.group(1).strip()

        # --- URL validation ---
        if not url.startswith("http://") and not url.startswith("https://"):
            label_issue(number, "needs-review")
            close_issue(number, "URL must start with http:// or https://.")
            continue

        if len(url) > 2048:
            label_issue(number, "needs-review")
            close_issue(number, "URL exceeds maximum length of 2048 characters.")
            continue

        # HEAD request to verify URL is reachable
        # Many sites block HEAD or bot User-Agents (403), so only flag on
        # connection failures or 5xx errors. 403/404 from known-good domains
        # are accepted — the URL will be verified again when fetched by agents.
        try:
            req = Request(url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0 (compatible; Seedlist/1.0)")
            resp = urlopen(req, timeout=10)
            status = resp.status
        except HTTPError as e:
            status = e.code
        except (URLError, OSError) as e:
            label_issue(number, "needs-review")
            reason = str(e)[:200]
            run_gh([
                "issue", "comment", str(number),
                "--body", f"Could not reach URL: {reason} — flagged for manual review.",
            ])
            continue

        if status >= 500:
            label_issue(number, "needs-review")
            run_gh([
                "issue", "comment", str(number),
                "--body", f"URL returned HTTP {status} — flagged for manual review.",
            ])
            continue

        # --- Find or create profile ---
        profile_path = find_profile(slug)
        if profile_path is None:
            # Infer profile type from issue body, default to startup
            inferred_type = profile_type if profile_type in ("investor", "firm", "startup") else "startup"
            type_dir_map = {"investor": "investors", "firm": "firms", "startup": "startups"}
            subdir = type_dir_map.get(inferred_type, "startups")
            profile_path = DATA / subdir / f"{slug}.md"
            profile_path.parent.mkdir(parents=True, exist_ok=True)

            # Create minimal stub with pending_sources — never lose the URL
            stub_meta = {
                "name": slug.replace("-", " ").title(),
                "slug": slug,
                "type": inferred_type,
                "status": "draft",
                "last_researched": TODAY_STR,
                "pending_sources": [{
                    "url": url,
                    "added": TODAY_STR,
                    "status": "queued",
                }],
            }
            if inferred_type == "startup":
                stub_meta.update({"founders": [], "investors": [], "firms": [], "sector": []})
            post_new = frontmatter.Post("", **stub_meta)
            with open(profile_path, "w") as f:
                f.write(frontmatter.dumps(post_new))

            # Also add to research queue so agents pick it up
            queue_data = load_queue()
            queue_list = queue_data.get("queue", [])
            # Dedup check
            existing_slugs_q = {
                re.sub(r"[^\w\-]", "-", item.get("name", "").lower()).strip("-")
                for item in queue_list
            }
            if slug not in existing_slugs_q:
                queue_list.append({
                    "name": stub_meta["name"],
                    "type": inferred_type,
                    "source": f"user-submitted source URL (issue #{number})",
                    "priority": "high",
                    "status": "pending",
                    "added": TODAY_STR,
                })
                queue_data["queue"] = queue_list
                save_queue(queue_data)

            close_issue(number, f"Created stub profile for {slug} with your source URL queued for research. Thank you for improving Seedlist!")
            print(f"    Created stub {slug} with pending source")
            continue

        # --- Add to pending_sources ---
        post = frontmatter.load(str(profile_path))
        pending = post.metadata.get("pending_sources", [])
        if pending is None:
            pending = []

        # Check for duplicate URL
        existing_urls = {s.get("url", "") for s in pending if isinstance(s, dict)}
        if url in existing_urls:
            close_issue(number, f"URL already in pending sources for {slug}. Skipping duplicate.")
            continue

        pending.append({
            "url": url,
            "added": TODAY_STR,
            "status": "queued",
        })
        post.metadata["pending_sources"] = pending

        with open(profile_path, "w") as f:
            f.write(frontmatter.dumps(post))

        close_issue(number, f"Added to pending sources for {slug}. Thank you for improving Seedlist!")
        print(f"    Added source to {slug}")


# ---------------------------------------------------------------------------
# CSV candidate processing
# ---------------------------------------------------------------------------

def process_candidate_issues():
    """Process issues labeled 'csv-unmatched'."""
    try:
        raw = run_gh([
            "issue", "list",
            "--label", "csv-unmatched",
            "--state", "open",
            "--json", "number,title,body",
            "--limit", "20",
        ])
    except subprocess.CalledProcessError as e:
        print(f"  Failed to list csv-unmatched issues: {e}")
        return

    if not raw:
        print("  No csv-unmatched issues found.")
        return

    issues = json.loads(raw)
    queue_data = load_queue()
    queue_list = queue_data.get("queue", [])

    # Build set of existing queue names (lowercased) for dedup
    queue_names = set()
    for item in queue_list:
        n = item.get("name", "")
        if n:
            queue_names.add(n.lower())

    # Build set of existing profile slugs
    existing_slugs = set()
    for subdir in ("investors", "firms", "startups"):
        d = DATA / subdir
        if d.exists():
            for p in d.glob("*.md"):
                existing_slugs.add(p.stem)

    queue_modified = False

    for issue in issues:
        number = issue["number"]
        body = issue.get("body", "") or ""
        print(f"  Processing issue #{number}...")

        # Parse candidates from body
        name_matches = re.findall(r'-\s*name:\s*"([^"]*)"', body)
        firm_matches = re.findall(r'firm:\s*"([^"]*)"', body)

        # Build candidate list: pair names with firms (firms list may be shorter)
        candidates = []
        for i, name in enumerate(name_matches):
            firm = firm_matches[i] if i < len(firm_matches) else ""
            candidates.append({"name": name, "firm": firm})

        total = len(candidates)
        added = 0
        skipped = 0

        for candidate in candidates:
            raw_name = candidate["name"]
            raw_firm = candidate["firm"]

            # Sanitize name
            clean_name = re.sub(r"[^\w\s\-\.']", "", raw_name)[:100].strip()
            if not clean_name:
                skipped += 1
                continue

            # Sanitize firm
            clean_firm = re.sub(r"[^\w\s\-\.']", "", raw_firm)[:100].strip()

            # Dedup: check queue names
            if clean_name.lower() in queue_names:
                skipped += 1
                continue

            # Dedup: check slug equivalent
            slug_equiv = re.sub(r"[^\w\-]", "-", clean_name.lower()).strip("-")
            slug_equiv = re.sub(r"-+", "-", slug_equiv)
            if slug_equiv in existing_slugs:
                skipped += 1
                continue

            # Name validation
            if not looks_like_name(clean_name):
                skipped += 1
                continue

            # Add to queue
            entry = {
                "name": clean_name,
                "type": "individual",
                "source": "user-submitted via CSV upload",
                "priority": "low",
                "status": "pending",
                "added": TODAY_STR,
            }
            if clean_firm:
                entry["firm"] = clean_firm

            queue_list.append(entry)
            queue_names.add(clean_name.lower())
            added += 1
            queue_modified = True

        # Build closing comment
        comment = f"Processed: {added} of {total} candidates added to research queue. Thank you for improving Seedlist!"
        if skipped > 0:
            comment += f" (Skipped {skipped} duplicates or invalid names)"

        close_issue(number, comment)
        print(f"    Added {added}/{total} candidates, skipped {skipped}")

    if queue_modified:
        queue_data["queue"] = queue_list
        save_queue(queue_data)
        print("  Queue updated.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_suggestion_issues():
    """Process issues labeled 'suggestion' — add to research queue."""
    try:
        raw = run_gh([
            "issue", "list",
            "--label", "suggestion",
            "--state", "open",
            "--json", "number,title,body",
            "--limit", "20",
        ])
    except subprocess.CalledProcessError as e:
        print(f"  Failed to list suggestion issues: {e}")
        return

    if not raw:
        print("  No suggestion issues found.")
        return

    issues = json.loads(raw)
    pending_path = DATA / ".pending-queue-adds.yaml"
    pending = []
    if pending_path.exists():
        pending = yaml.safe_load(pending_path.read_text()) or []

    for issue in issues:
        number = issue["number"]
        body = issue.get("body", "") or ""
        print(f"  Processing suggestion #{number}...")

        # Parse query from body — try structured field first, fall back to title
        query_match = re.search(r"^query:\s*(.+)$", body, re.MULTILINE)
        type_match = re.search(r"^type:\s*(.+)$", body, re.MULTILINE)

        if query_match:
            query = query_match.group(1).strip()
        else:
            # Fall back to issue title (strip "Suggestion: " prefix)
            title = issue.get("title", "")
            query = re.sub(r"^Suggestion:\s*", "", title, flags=re.IGNORECASE).strip()
            if not query:
                # Last resort: extract first non-comment, non-metadata line from body
                for line in body.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("<!--") and not line.startswith("submitted:") and not line.startswith("page:"):
                        query = line
                        break

        if not query:
            print(f"    Skipping #{number}: could not extract suggestion")
            continue

        entity_type = type_match.group(1).strip() if type_match else "individual"

        # Sanitize: only allow alphanumeric, spaces, hyphens, periods, ampersands
        query = re.sub(r"[^\w\s\-\.&,']", "", query).strip()
        if not query or len(query) > 200:
            print(f"    Skipping #{number}: invalid query")
            continue

        # Guess type from keywords
        firm_keywords = ("ventures", "capital", "partners", "fund", "group", "investment")
        query_lower = query.lower()
        if any(kw in query_lower for kw in firm_keywords):
            entity_type = "firm"

        pending.append({
            "name": query,
            "type": entity_type,
            "priority": "normal",
            "source": f"user suggestion (issue #{number})",
            "discovered_from": "user-suggestion",
        })

        # Close the issue
        try:
            run_gh(["issue", "close", str(number), "--comment",
                    f"Added to research queue. Thanks for the suggestion!"])
            print(f"    Queued and closed #{number}: {query}")
        except subprocess.CalledProcessError:
            print(f"    Queued #{number} but failed to close issue")

    if pending:
        pending_path.write_text(yaml.dump(pending, default_flow_style=False, allow_unicode=True))
        print(f"  Wrote {len(pending)} items to .pending-queue-adds.yaml")


def main():
    print("Processing source submissions...")
    process_source_issues()
    print("Processing CSV candidates...")
    process_candidate_issues()
    print("Processing suggestions...")
    process_suggestion_issues()
    print("Done.")


if __name__ == "__main__":
    main()
