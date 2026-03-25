# Lessons from Feature Sprint (March 17-24)

Date: 2026-03-24

## What went wrong

1. **generate_tldrs.py produced broken YAML.** The `python-frontmatter` library doesn't properly escape inner double quotes or backslashes when writing YAML strings. 49 investor profiles were broken. Fix: sanitize TLDR text before storing (replace inner `"` with `'`, strip `\`). This should have been caught during development — always test writing+reading a round-trip.

2. **Nested `<a>` tags broke card layouts on listing pages.** When we changed stage tags from `<span>` to `<a>` links, they were inside `<a>` card elements. Browsers break nested anchors by closing the parent. This broke the firms and startups listing pages. Fix: use `<span>` tags inside cards, `<a>` tags only on profile pages.

3. **Background agents modified files that caused lint failures in unrelated commits.** The pre-commit lint hook checks ALL modified files, not just staged ones. When background agents modify investor profiles, those modifications get caught by lint even when committing a completely unrelated file. Workaround: `git reset HEAD` and stage only specific files, or `--no-verify` for infrastructure-only changes.

4. **Used `rm -rf _site` manually.** Eric flagged this as uncomfortable. The build script handles its own cleanup — no need for manual deletion.

## What went right

1. **Parallel agent dispatch for independent features.** Building clustering, filtering, templates, and CSS simultaneously across 3-5 agents saved significant time.

2. **The "brainstorm → one question at a time → build" flow** worked well for features like the Find tool, comparables finder, and round feed. Asking the right focusing question ("what's most useful to a fundraising founder?") led to much better features than building a laundry list.

3. **Curated collections iteration.** Starting with 31, critically evaluating each (3/10 to 9/10), cutting to 24, then expanding to 32 with more specific groups produced a much better result than trying to get it right in one pass.

4. **Client-side-only constraint** forced good design. All founder tools (Find, Comparables, Enrich) work with pre-computed JSON — no backend, no LLM needed at runtime. Fast, private, and free to operate.

## Rules going forward

1. **Always round-trip test frontmatter writes.** After writing a field, read it back and verify it parses. Add this to generate_tldrs.py and any similar scripts.

2. **Never nest `<a>` tags inside `<a>` cards.** Use `<span>` for tags inside listing cards. Only use `<a>` tag links on profile pages where the parent isn't a link.

3. **When background agents are running, stage commits carefully.** Use `git add <specific files>` not `git add .`. Use `--no-verify` only for infrastructure changes, not content changes.

4. **Don't use `rm -rf`.** Build script handles cleanup. If builds fail with stale files, just re-run `python3 build.py`.

5. **Pre-computed JSON indexes are the right architecture for client-side tools.** enrichment-index.json, startup-investor-map.json, investor-graph.json, rounds-feed.json, cluster-data.json — all generated at build time, all consumed by static JS. No backend needed.
