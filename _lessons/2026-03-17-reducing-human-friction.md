# Lessons from Reducing Human-in-the-Loop Friction

Date: 2026-03-17

## Friction sources identified

1. **Post-agent manual labor** — After every batch, the orchestrator manually: parsed QUEUE_ADD lines from agent output, ran fix-citations on each slug, fixed missing `firm:` fields, fixed missing portfolio years, ran batch-publish, committed queue changes. This entire sequence is mechanical and should be scripted.

2. **Queue management was manual** — Parsing `QUEUE_ADD: name=X, type=Y, firm=Z` lines from agent output and manually appending to queue.yaml with dedup checking. Now handled by `sl queue-add`.

3. **Common lint failures that should auto-fix** — 80% of lint failures were: missing `firm:` field (always `independent` for angels), duplicate source URLs (already handled by fix-citations), missing portfolio years. Now handled by `sl auto-fix`.

4. **Artificial batch limit** — CLAUDE.md said "stop after 3 consecutive batches." This forced Eric to say "keep going" every 3 batches. Removed — stop only when queue is exhausted.

5. **Verbose status reporting** — Multi-line status blocks between batches created implicit "waiting for acknowledgment" pauses. Replaced with single-line format.

6. **Agent prompts included Bash commands** — Agents that run Bash commands hit permission prompts. Agents should do research+write ONLY. All Bash (lint, fix, git) stays in orchestrator.

7. **Agents dispatched with boilerplate** — Each agent dispatch repeated 500+ words of format instructions. Should be templatized.

## What went right

1. `batch-publish` and `fix-citations` eliminated commit cascades entirely
2. Anti-hallucination rules dramatically reduced fabricated URLs and invented percentages
3. Sources-first workflow is a structural fix for citation quality
4. Background agent pattern (research+write only) avoids permission friction

## Rules going forward

1. **Agents do research+write ONLY.** No Bash, no lint, no git. Orchestrator handles all post-processing.
2. **Use `sl queue-add` for queue management.** Never manually edit queue.yaml for additions.
3. **Use `sl auto-fix` before `sl batch-publish`.** This catches mechanical issues before lint runs.
4. **No artificial batch limits.** Run until queue is exhausted.
5. **One-line status updates.** No multi-line reports, no implicit pauses.
6. **Every new `sl` command should be idempotent.** Running it twice should be safe.
