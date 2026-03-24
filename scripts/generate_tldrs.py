#!/usr/bin/env python3
"""Generate TLDR summaries for investor profiles using Claude API."""

import argparse
import sys
import os
import time
from pathlib import Path
import frontmatter
import anthropic

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SYSTEM_PROMPT = (
    "You are a concise writer helping founders evaluate investors. "
    "Generate a 2-4 sentence TLDR summary of this investor profile. "
    "Focus on: who they are (one line), what they actually invest in "
    "(from inferred thesis, not stated), what makes them distinctive "
    "(speed, check size, sector expertise, founder preferences), and "
    "their most notable investments. Write in third person, present tense. "
    "No bullet points. No fluff. Every sentence should help a founder "
    "decide whether to pitch this person."
)


def generate_tldr(content: str, client: anthropic.Anthropic) -> str:
    """Generate a TLDR from profile content."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text.strip()


def build_full_content(post) -> str:
    """Reconstruct full markdown content from a frontmatter post."""
    lines = ["---"]
    for key, value in post.metadata.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(post.content)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate TLDR summaries for investor profiles.")
    parser.add_argument("--dry-run", action="store_true", help="Print TLDRs without writing them to files.")
    parser.add_argument("--limit", type=int, default=None, help="Only process N profiles.")
    args = parser.parse_args()

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    profiles = sorted(DATA.glob("investors/*.md"))
    to_process = []

    for path in profiles:
        post = frontmatter.load(str(path))
        if post.metadata.get("status") != "published":
            continue
        if post.metadata.get("tldr"):
            continue
        to_process.append(path)

    if args.limit is not None:
        to_process = to_process[: args.limit]

    print(f"Found {len(to_process)} profiles needing TLDRs")

    if len(to_process) == 0:
        return

    generated = 0

    for i, path in enumerate(to_process):
        post = frontmatter.load(str(path))
        name = post.metadata.get("name", path.stem)
        print(f"  [{i + 1}/{len(to_process)}] {name}...", end=" ", flush=True)

        try:
            full_content = build_full_content(post)
            tldr = generate_tldr(full_content, client)

            # Clean up: remove any surrounding quotes the model might add
            tldr = tldr.strip('"').strip("'")

            if args.dry_run:
                print(f"PREVIEW ({len(tldr)} chars)")
                print(f"    tldr: \"{tldr}\"")
            else:
                # Escape inner double quotes for YAML safety
                post.metadata["tldr"] = tldr
                with open(path, "w") as f:
                    f.write(frontmatter.dumps(post))
                print(f"OK ({len(tldr)} chars)")

            generated += 1

        except Exception as e:
            print(f"ERROR: {e}")
            continue

        # Rate limiting between calls
        if i < len(to_process) - 1:
            time.sleep(0.5)

    action = "Previewed" if args.dry_run else "Generated"
    print(f"\nDone. {action} {generated} TLDRs.")


if __name__ == "__main__":
    main()
