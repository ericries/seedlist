# Lessons from Progress Reflection and Tooling Improvements

Date: 2026-03-17

## What went wrong

1. **7 completed profiles sat uncommitted across sessions.** Background agents wrote profiles but couldn't lint/commit. The orchestrator needs to always commit+publish at the end of a session, even if agents failed their lint step.

2. **13 draft firm profiles were neglected.** The investor-first pipeline correctly prioritized investors, but let firms pile up as drafts. These firms had already been researched and written — the only blocker was publishing. Should have been a 5-minute batch-publish operation.

3. **Lint percentage heuristic produced false positives on every firm.** The naive "sum all percentages" approach doesn't work when profiles have multiple distinct breakdowns (sector, stage, geography). Fixed to only flag bullet-list categorical breakdowns.

4. **Python path issue recurred.** Even after documenting the Cellar path, the default `python3` still lacks required packages. Adding `Bash(/usr/local/Cellar/python*)` to permissions helps but doesn't fix the root cause.

## What went right

1. **batch-publish and fix-citations worked perfectly.** Published 7 investors (7/7 clean) and 13 firms (13/13) with auto-fixed citations. Single commit per batch.

2. **Anti-hallucination rules are comprehensive.** The 7 rules added to CLAUDE.md address every documented failure mode from previous batches.

3. **Sources-first workflow is a structural fix.** Instead of writing text and backfilling citations (which leads to fabricated URLs), agents now build the source list first and write from it.

## Rules going forward

1. **At end of every session, commit and push ALL pending work.** Never leave uncommitted profiles.
2. **Review draft firm profiles weekly.** They accumulate because the pipeline deprioritizes them, but publishing is usually trivial.
3. **Lint heuristics should have low false-positive rates.** A warning that fires on every profile teaches agents to ignore warnings. Better to miss some issues than cry wolf.
4. **When dispatching fix agents for flagged profiles, explicitly list each issue to fix.** The more specific the prompt, the fewer hallucinated "fixes."
