# Lessons from CLI Toolkit Development

Date: 2026-03-14

## What went wrong
1. Every status check required ad-hoc Python one-liners piped through yaml parsing
2. Profile status changes (publish, flag, draft) were done with inconsistent sed/python commands
3. Queue counting required different grep/python combos each time
4. Git operations (add, commit, push) were repeated as raw commands with varying patterns
5. No single command to check repo health (uncommitted changes, unpushed commits, build status)
6. Each agent had to figure out git/build/status commands from scratch

## What went right
1. The two-pass review workflow caught real issues (misattributed quotes, dead URLs, math errors)
2. Parallel agent execution maximized throughput
3. Priority tier system correctly prioritized angels/solos over firm partners

## Rules going forward
1. Always use `scripts/sl` for common operations instead of ad-hoc commands
2. When a new repeated operation pattern emerges, add it to `scripts/sl` rather than writing one-off commands
3. Agent prompts should reference `scripts/sl` commands (e.g., "run `python3 scripts/sl publish {slug}`")
4. Keep commands idempotent — `sl publish` on an already-published profile is a no-op, not an error
5. After every batch, review whether any new ad-hoc patterns emerged that should be added to the toolkit
