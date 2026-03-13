# Lessons from Wave 1 Startup Profiles (20 companies)

Date: 2026-03-13

## What went wrong

1. **Citation duplication** — 3 of 20 startup profiles (Slack, Snapchat, Pinterest) had duplicate source URLs requiring complete source section rewrites. This happens when research agents pull the same information from a source for different claims and assign separate footnote numbers.
2. **Quote misattribution** — Okta had investor quotes in the "What Investors Say" section that were actually founder quotes (Frederic Kerrest). PayPal had Peter Thiel in both sections. Need clearer separation of founder vs investor voices.
3. **Overly detailed startup profiles** — Initial profiles included extensive narrative about founding stories, product pivots, and market context. User feedback: startup profiles should be lean — just enough data for investor thesis inference (funding rounds, investor lists, sector, status).
4. **Malformed quotes** — Figma had a Danny Rimer quote that was actually paraphrased/reworded rather than a direct quote. Fixed to factual statement about seed-to-IPO returns.

## What went right

1. **Parallel batch processing** — 5 concurrent research agents + 5 concurrent review agents worked well for 20 startups with no file conflicts (co-investor data written to separate batch files).
2. **Two-pass review caught real issues** — 7 of 20 profiles were flagged during review. All issues were fixable. The review pass is essential.
3. **Co-investor extraction** — Successfully extracted co-investors from all 20 startups, identified 21 firms and 4 individuals appearing across 2+ startups, and added them to queue as Wave 2 entries.
4. **Cross-linking works** — Startup pages correctly link to investor and firm profiles where they exist.

## Rules going forward

1. **Startup profiles should be lean** — Focus on: funding rounds (date, amount, stage, lead, co-investors), sector classification, company status, investor lists per round. Keep About sections to 2-3 sentences. Skip extensive founder quotes unless they relate to the investment process.
2. **Deduplicate sources before writing** — Each URL should appear exactly once. Build the source list first, then assign footnotes.
3. **Strictly separate founder vs investor quotes** — Before publishing, verify every quote in "What Investors Say" is from a non-founder investor, and every quote in "What Founders Say" is from a founder.
4. **No paraphrases as quotes** — If a direct quote cannot be verified, present the information as a factual statement instead.
5. **Run citation hygiene as part of review** — The review pass must explicitly check: no duplicate URLs, sequential numbering, no gaps, every footnote referenced, every reference has a footnote.
