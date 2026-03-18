# Lessons: Required Agent Prompt Instructions

Date: 2026-03-18

## Problem

9 of 14 profiles across 2 batches failed lint because agents left portfolio years blank. The CLAUDE.md has the rule but agents don't read CLAUDE.md — they only see the dispatch prompt.

## Required additions to every agent dispatch prompt

The following text MUST appear in every research agent prompt. These are not suggestions — omitting any of them causes lint failures that require manual fixes.

```
PORTFOLIO TABLE RULES:
- Every row MUST have a year. Use ~YYYY (approximate founding year) if exact date unknown.
- NEVER use — or -- or "Undisclosed" for the year column. Always estimate.
- For public equity holdings (13F data), use the reporting period year (e.g., 2025 for Q4 2025).
- If you cannot even estimate a year, do not include the row.
- Table headers must start with | Company or | Fund (not arbitrary column names).
```

## Also required

```
- If the file already exists at the target path with status: published, do NOT overwrite.
  Instead, report what updates you would make.
```

## Why this matters

Each missing year requires a manual Edit call to fix. With 8 agents per batch and ~6 failures per batch, that's 30-50 manual edits per batch — the single biggest source of post-agent labor.
