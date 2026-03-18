# Lessons from Batch 2: File-Based Workflow Test

Date: 2026-03-17

## What went wrong

1. **Missing portfolio years: still the #1 lint failure.** 3 of 6 profiles in batch 1 failed on this. Agents write "—" or "Undisclosed" for years they can't find. The CLAUDE.md instruction to use `~YYYY` exists but agents ignore it. Need to add this to the agent dispatch prompt explicitly.

2. **Public equity holdings tables break lint.** Crossover investors (Chase Coleman, Philippe Laffont) have 13F holdings without investment years. Lint flags every `|` row without a year. Two fixes needed: (a) agents should always include a Year column even for public holdings (use reporting period), (b) lint should recognize "Top Public Equity Holdings" sub-tables.

3. **post-batch exited error on partial success.** Published 3 clean profiles but exited code 1 because 3 others failed lint. The git commit for passing profiles succeeded, but the error exit made it look like total failure. Should exit 0 when some profiles publish, and report failures as warnings.

4. **Bill Gurley agent overwrote published profile.** Dispatched twice (original was slow), second agent updated already-published file. Agents should check file status before overwriting.

5. **Auth expiry killed Peter Fenton agent after 62 tool uses.** Zero output saved. Agents should write partial progress so work isn't lost.

## What went right

1. **File-based post-batch works perfectly.** Write 2 YAML files → one `sl post-batch` call → queue adds + completions + auto-fix + lint + publish + rebuild + commit + push. One permission prompt total.

2. **queue-add dedup catches duplicates reliably.** 3 of 8 additions in batch 1 were already in queue — caught automatically.

3. **auto-fix caught citation issues.** Chetan Puttagunta had 1 duplicate URL, Yuri Milner had 3 — all fixed automatically before lint.

4. **The iteration loop itself is working.** Each batch teaches what to automate next. Manual → batch-publish → post-batch → file-based post-batch in one session.

## Rules going forward

1. **Agent prompts MUST include:** "Every portfolio row MUST have a year. Use ~YYYY (approximate founding year) if exact date unknown. NEVER use — or Undisclosed for the year column."
2. **Agent prompts MUST include:** "If a profile already exists at the target path and has status: published, do NOT overwrite. Instead report what updates you would make."
3. **post-batch should exit 0 on partial success.** Only exit non-zero if zero profiles publish AND there were drafts to process.
4. **Public holdings tables should include a Year column** with the 13F reporting period (e.g., 2025 for Q4 2025 data).
