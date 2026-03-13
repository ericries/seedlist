# Lessons from First Batch (Ron Conway, Mike Maples, Shaherose Charania)

Date: 2026-03-13

## What went wrong

1. **Inferred thesis was restated thesis.** Agents paraphrased the stated thesis and added fake percentages (~30%, ~20%) with no denominator. The inferred thesis must be independent analysis computed from counted portfolio data.

2. **Portfolio tables were thin.** Ron Conway: 33 of 700+ (4.7%). Mike Maples: 21 of 247+ (8.5%). Shaherose: 5 of 40+ (12.5%). Must aim for 50%+ or explicitly state the gap.

3. **Dates were vague.** "Early stage" and "--" are useless. Every entry needs a year — use company founding year as proxy if investment year is unknown.

4. **Founder quotes were padded.** Agents filled "What Founders Say" with the investor's own anecdotes, firm marketing copy, or process descriptions. These are NOT founder quotes. Dedicated search effort is required.

5. **Citation hygiene was poor.** Duplicate sources, skipped footnote numbers, 403 URLs kept with notes, orphan footnotes. The fix pass didn't catch all of these.

6. **Research agents hallucinate citations.** First-pass agents generated fake URLs and misattributed quotes. The two-pass review caught these but the fix pass sometimes introduced new issues.

7. **SV Angel website testimonials are biased.** All Ron Conway "founder quotes" came from svangel.com — the firm's own marketing page. Need independent sources.

## What went right

1. **Two-pass review workflow works.** Every profile was flagged with real issues. The review agents caught hallucinated citations, misattributed quotes, and unsourced claims.

2. **Parallel agent execution is fast.** Three profiles researched simultaneously, three reviewed simultaneously, three fixed simultaneously.

3. **The spec-driven approach works.** Having a clear data format and section structure meant agents produced consistently structured output.

## Rules going forward

- Never present estimated percentages without showing the math (N total, X in category = Y%)
- Every portfolio entry needs a year — founding year proxy marked with "~YYYY (founded)" if investment year unknown
- "What Founders Say" must contain only actual quotes from founders, never investor anecdotes or firm marketing
- Run citation hygiene check: sequential numbering, no duplicates, no dead URLs, no orphans
- After every batch, write a new lesson file before starting the next batch
