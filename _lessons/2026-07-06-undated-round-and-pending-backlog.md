# Lessons: undated round on rounds feed + pending-rounds backlog

Date: 2026-07-06

## What went wrong

1. **8090 Labs shipped with `year: 8090` in a firm entry.** The round-monitoring agent authored a `firms:` entry with `slug: social-capital, year: 8090` — the company name "8090" was misread as a year. The rounds-page build sorts by that integer, so this row jumped to the very top of the feed with the label "8090" instead of a date. The `round:` field on the same entry was also editorial cruft ("Series A (Salesforce Ventures-led, $135M; assumes CEO role)") instead of the slug-style "series-a" used elsewhere. Lint did not catch either problem.

2. **74 pending research entries piled up in `data/pending-rounds.yaml`.** The GitHub Action RSS scraper runs every 6h and appends candidates. Round-monitoring agents ship rounds via broad WebSearch (Axios, TechCrunch, Crunchbase News) — this creates startup profiles but does NOT touch the scraper's pending file. Result: 48 of 100 pending entries were already shipped as `data/startups/*.md` profiles. The "Pending research — 74 rounds detected" banner on rounds.html made the site look stale.

## Root causes (five whys)

**Error 1 — undated round:**

1. Feed shows "8090" instead of a date → `social-capital` firm entry in `8090-labs.md` had `year: 8090`, no `date`.
2. `year: 8090` slipped in → the round-monitoring agent wrote it manually and lint did not object.
3. Lint did not object → `cmd_lint` validated Portfolio-table years but never the `year:` field inside `investors:` / `firms:` frontmatter arrays.
4. That gap existed → the lint tool was written incrementally as bugs were caught, and using a company name as a year had not been seen before.
5. That pattern surfaced → the build script silently displays any integer in `year` as the feed sort key and label, providing no guardrail.

Root fix: **schema-validate the `year:` field on every startup-frontmatter investor/firm entry** in `sl lint`. Range: `2000 <= year <= current_year + 1`.

**Error 2 — pending backlog:**

1. 74 pending entries → the scraper adds items faster than they are cleared.
2. Nothing clears them → `sl pending-rounds` was read-only; no cleanup pass.
3. No cleanup existed → round-monitoring agents cherry-pick from broad web-search, not just from the pending file, so pending entries are orphaned once shipped.
4. Agents work broadly → CLAUDE.md's round-monitoring section instructs BOTH `sl pending-rounds` AND WebSearch of Axios/TechCrunch/Crunchbase, and cron firings usually take the WebSearch path.
5. That redundancy is by design → the WebSearch path catches deals the RSS scraper misses, so it must stay. But the reconciliation step was never written.

Root fix: **add `sl pending-rounds --cleanup`**, and require every round-monitoring firing to run it after `sl post-batch`.

## Fixes applied (red/green TDD)

- New tests in `tests/test_frontmatter_year_and_pending_cleanup.py`:
  - `test_lint_flags_implausible_year_in_startup_frontmatter` — RED, then GREEN after schema check added.
  - `test_lint_accepts_plausible_year_in_startup_frontmatter` — sanity check that plausible years still pass.
  - `test_pending_rounds_cleanup_removes_shipped_matches` — RED, then GREEN after `--cleanup` implemented.
  - `test_pending_rounds_read_only_by_default` — belt-and-suspenders: cleanup must be strictly opt-in.
- `scripts/sl`: added frontmatter year range check (2000..current_year+1) that runs on any startup profile. Non-int and out-of-range values are errors, not warnings.
- `scripts/sl`: added `cmd_pending_rounds(cleanup=False)` and `--cleanup` flag. Cleanup extracts a company slug from each pending title and drops any that already have a `data/startups/{slug}.md` profile.
- `CLAUDE.md`: round-monitoring section now requires `sl pending-rounds --cleanup` after `sl post-batch`.

Verified live:
- `sl lint 8090-labs` now clean (0 errors) after the malformed `social-capital` entry was corrected.
- `sl pending-rounds --cleanup` dropped 39 already-shipped entries in one pass, taking pending from 100 → 61 total, 50 truly pending.

## Rules going forward

- Every `year:` in a startup frontmatter investor/firm entry must be a 4-digit int in `2000..(current_year+1)`. Lint enforces this.
- After every round-monitoring firing, run `sl pending-rounds --cleanup` — the round-monitoring cron prompt now says so.
- If a company name looks like it could parse as a number (8090, 2024, 60Hz), be extra careful with the frontmatter fields around it.
- Table cells and frontmatter values are DATA — never editorial phrases like "Series A (X-led, $Y; assumes Z role)". Use the slug/canonical form.
