# Lessons from User Feedback & CSV-to-Queue Pipeline

Date: 2026-03-17

## What went wrong

1. **Jumped straight to implementation without checking user assumptions.** The original plan used GitHub Issues requiring auth. Eric pushed back asking if there was a simpler no-auth option. Should have surfaced this tradeoff during planning, not after plan was written.

2. **Agent-generated code used inline styles instead of CSS classes.** The feedback.js agent created forms with `style.cssText` inline styles, even though a separate agent was adding proper CSS classes to style.css. Had to manually fix this after agent completion. When dispatching parallel agents for related UI work (JS + CSS), the JS agent prompt must explicitly say "use these CSS class names" rather than letting it invent inline styles.

3. **Python environment fragility.** `build.py` and `scripts/sl` require `python-frontmatter`, `pyyaml`, `jinja2`, etc. but there's no venv checked in or documented setup. Had to create a temp venv to verify the build. This will bite every new session.

4. **Didn't write tests.** The plan called for tests (step 7) but I didn't implement them. The CLI commands (`review-sources`, `review-candidates`) and the JS functions (URL validation, name heuristics, GitHub issue URL construction) all have testable logic.

## What went right

1. **Parallel agent dispatch worked well.** Five agents running concurrently (feedback.js, CSS, templates, enrich changes, CLI commands) completed in ~70 seconds total. All produced correct, non-conflicting code.

2. **Brainstorming alternatives with the user before committing.** Eric asked about no-auth alternatives, we discussed pros/cons of GitHub Issues vs form backends vs mailto, and landed on the right choice (GitHub Issues for now) with clear reasoning. The conversation took 2 messages but saved potential rework.

3. **Security model is clean.** URL-only input, name sanitization, GitHub auth as spam filter, human review before queue, hardcoded source fields — no user text ever reaches research agents.

4. **Build verification caught nothing broken.** Running `python3 build.py` after all agents completed confirmed everything wired up correctly.

## Rules going forward

1. **When dispatching parallel UI agents (JS + CSS), share the CSS class names explicitly in the JS agent prompt.** Don't let them independently invent styles.

2. **Surface auth/access requirements during planning.** Any feature that requires user accounts should flag that tradeoff early — "this requires X account, is that acceptable?"

3. **Always verify build after multi-agent implementation.** Run `python3 build.py` and check a generated page before declaring done.

4. **Test CLI commands that interact with external services (gh) by at least verifying they parse/route correctly.** Run `sl` with no args to confirm help text, and `python3 -c "import py_compile; py_compile.compile('scripts/sl', doraise=True)"` for syntax.

5. **Document Python environment setup or note it as tech debt.** A `requirements.txt` or setup script would prevent repeated venv creation across sessions.
