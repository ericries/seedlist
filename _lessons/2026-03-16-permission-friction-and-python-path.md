# Lessons from Batch 5: Permission Friction and Python Path Issues

Date: 2026-03-16

## What went wrong

1. **All 7 background research agents failed to run lint** because Bash permissions blocked the full Python path `/usr/local/Cellar/python@3.10/.../python3`. The settings had `Bash(python3 *)` but agents resolved to the full Cellar path, which didn't match the glob pattern.

2. **`python3` on $PATH points to `/usr/local/bin/python3` which lacks yaml/frontmatter.** The correct Python with all dependencies is at `/usr/local/Cellar/python@3.10/3.10.6_2/Frameworks/Python.framework/Versions/3.10/bin/python3`. This means `python3 scripts/sl *` also fails when run from the main orchestrator context — the first lint attempt errored with `No module named 'yaml'`.

3. **Agents couldn't self-fix** because the lint step was blocked by permissions, so they couldn't enter the fix-lint-recheck loop. They each independently asked for permission, wasting time.

4. **Commit-per-file pattern caused pre-commit hook cascades in earlier batches.** When one agent's file had lint errors, staging it alongside other files caused ALL commits to fail.

## What went right

1. All 7 agents successfully wrote profiles that passed lint on first check (after running lint externally).
2. The parallel agent pattern works well — 7 profiles researched concurrently.
3. Profile quality was high: clean citations, proper sections, accurate attribution.

## Rules going forward

1. **Always use the Cellar Python path for sl commands**, OR ensure `Bash(/usr/local/Cellar/python*)` is in permissions. Fixed in settings.local.json.
2. **Use `sl batch-publish` instead of per-file commits.** New command: lint + fix-citations + publish all profiles in one commit.
3. **Use `sl fix-citations` before lint.** Auto-fixes duplicate URLs, orphan defs, and renumbers footnotes.
4. **Background agents should NOT be expected to run Bash commands.** If an agent needs Bash, it will hit permission prompts. Design agent prompts to do research+write only; run lint/fix/publish from the orchestrator after agents complete.
5. **Test the Python path at the start of each session.** Run `python3 -c "import yaml"` to verify the default `python3` works, and if not, use the Cellar path explicitly.
