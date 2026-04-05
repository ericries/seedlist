"""Tests for permission-reducing fixes in scripts/sl:
1. _git_push_with_retry() is used instead of bare run("git push")
2. cmd_auto_fix adds missing required sections for startup profiles
3. cmd_write_pending writes .pending-queue-adds.yaml and .pending-completions.yaml
"""

import importlib.machinery
import importlib.util
import inspect
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import frontmatter
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# ── Import sl module ──
_sl_path = ROOT / "scripts" / "sl"
_loader = importlib.machinery.SourceFileLoader("sl", str(_sl_path))
spec = importlib.util.spec_from_loader("sl", _loader, origin=str(_sl_path))
sl = importlib.util.module_from_spec(spec)
sl.__file__ = str(_sl_path)
sys.modules["sl"] = sl
spec.loader.exec_module(sl)


# ===========================================================================
# Test 1: All git push calls use _git_push_with_retry
# ===========================================================================

class TestGitPushRetry:
    """Every function that pushes should use _git_push_with_retry, not bare run('git push')."""

    def test_git_push_with_retry_exists(self):
        assert hasattr(sl, "_git_push_with_retry")

    def test_cmd_ship_uses_retry(self):
        source = inspect.getsource(sl.cmd_ship)
        assert "_git_push_with_retry()" in source, "cmd_ship should use _git_push_with_retry()"
        # Should NOT have bare run("git push")
        bare_pushes = [line.strip() for line in source.split('\n')
                       if 'run("git push")' in line or "run('git push')" in line]
        assert len(bare_pushes) == 0, f"cmd_ship has bare git push: {bare_pushes}"

    def test_cmd_post_batch_uses_retry(self):
        source = inspect.getsource(sl.cmd_post_batch)
        assert "_git_push_with_retry()" in source, "cmd_post_batch should use _git_push_with_retry()"
        bare_pushes = [line.strip() for line in source.split('\n')
                       if 'run("git push")' in line or "run('git push')" in line]
        assert len(bare_pushes) == 0, f"cmd_post_batch has bare git push: {bare_pushes}"

    def test_cmd_draft_uses_retry(self):
        source = inspect.getsource(sl.cmd_draft)
        assert "_git_push_with_retry()" in source, "cmd_draft should use _git_push_with_retry()"
        bare_pushes = [line.strip() for line in source.split('\n')
                       if 'run("git push")' in line or "run('git push')" in line]
        assert len(bare_pushes) == 0, f"cmd_draft has bare git push: {bare_pushes}"

    def test_no_bare_git_push_anywhere(self):
        """Scan the entire sl source for bare run("git push") — they should all be replaced."""
        with open(ROOT / "scripts" / "sl") as f:
            full_source = f.read()
        # Find all lines with run("git push") that aren't inside _git_push_with_retry
        lines = full_source.split('\n')
        bare_pushes = []
        in_retry_func = False
        for i, line in enumerate(lines, 1):
            if 'def _git_push_with_retry' in line:
                in_retry_func = True
            elif in_retry_func and line and not line.startswith(' ') and not line.startswith('\t'):
                in_retry_func = False
            elif in_retry_func and re.match(r'^def ', line):
                in_retry_func = False

            if not in_retry_func and ('run("git push")' in line or "run('git push')" in line):
                bare_pushes.append(f"line {i}: {line.strip()}")

        assert len(bare_pushes) == 0, f"Found bare git push outside _git_push_with_retry:\n" + "\n".join(bare_pushes)


# ===========================================================================
# Test 2: Auto-fix adds missing required sections for startups
# ===========================================================================

class TestAutoFixMissingSections:
    """cmd_auto_fix should add missing required sections for startup profiles."""

    def test_auto_fix_adds_missing_startup_sections(self, tmp_path):
        """A startup profile missing 'What Investors Say' and 'What Founders Say'
        should get those sections added by auto-fix."""
        profile = tmp_path / "data" / "startups" / "test-startup.md"
        profile.parent.mkdir(parents=True)

        content = """---
name: Test Startup
slug: test-startup
type: startup
status: draft
---

## About

Test startup description [^1].

## Funding History

| Date | Round | Amount | Lead | Co-investors |
|------|-------|--------|------|-------------|
| 2025-01-15 | Seed | $5M | Acme Ventures | [^1] |

## Sources

[^1]: TechCrunch, accessed April 2026. https://techcrunch.com/test
"""
        profile.write_text(content)

        # Mock find_profile to return our temp file
        with patch.object(sl, 'find_profile', return_value=str(profile)):
            with patch.object(sl, 'cmd_fix_citations'):  # skip citation fixes
                sl.cmd_auto_fix("test-startup")

        result = profile.read_text()
        assert "## What Investors Say" in result
        assert "## What Founders Say" in result

    def test_auto_fix_does_not_duplicate_existing_sections(self, tmp_path):
        """If sections already exist, auto-fix should not add duplicates."""
        profile = tmp_path / "data" / "startups" / "test-startup.md"
        profile.parent.mkdir(parents=True)

        content = """---
name: Test Startup
slug: test-startup
type: startup
status: draft
---

## About

Test startup description [^1].

## Funding History

| Date | Round | Amount | Lead | Co-investors |
|------|-------|--------|------|-------------|
| 2025-01-15 | Seed | $5M | Acme Ventures | [^1] |

## What Investors Say

No investor quotes available yet.

## What Founders Say

No founder quotes available yet.

## Sources

[^1]: TechCrunch, accessed April 2026. https://techcrunch.com/test
"""
        profile.write_text(content)

        with patch.object(sl, 'find_profile', return_value=str(profile)):
            with patch.object(sl, 'cmd_fix_citations'):
                sl.cmd_auto_fix("test-startup")

        result = profile.read_text()
        # Count occurrences — should still be exactly 1 each
        assert result.count("## What Investors Say") == 1
        assert result.count("## What Founders Say") == 1

    def test_auto_fix_adds_missing_investor_sections(self, tmp_path):
        """Investor profiles missing required sections should also get them added."""
        profile = tmp_path / "data" / "investors" / "test-investor.md"
        profile.parent.mkdir(parents=True)

        content = """---
name: Test Investor
slug: test-investor
type: individual
firm: independent
status: draft
---

## Background

Some background [^1].

## Stated Thesis

Some thesis [^1].

## Portfolio

| Company | Year | Stage | Source |
|---------|------|-------|--------|
| TestCo | 2024 | Seed | [^1] |

## Sources

[^1]: Source, accessed April 2026. https://example.com/test
"""
        profile.write_text(content)

        with patch.object(sl, 'find_profile', return_value=str(profile)):
            with patch.object(sl, 'cmd_fix_citations'):
                sl.cmd_auto_fix("test-investor")

        result = profile.read_text()
        assert "## Inferred Thesis" in result
        assert "## In Their Own Words" in result
        assert "## What Founders Say" in result


# ===========================================================================
# Test 3: write-pending command
# ===========================================================================

class TestWritePending:
    """sl write-pending should create .pending-queue-adds.yaml and .pending-completions.yaml."""

    def test_write_pending_function_exists(self):
        assert hasattr(sl, "cmd_write_pending")

    def test_write_pending_creates_queue_adds(self, tmp_path):
        """write-pending --adds should write .pending-queue-adds.yaml."""
        adds_path = tmp_path / ".pending-queue-adds.yaml"
        adds_data = [
            {"name": "Jane Doe", "type": "individual", "firm": "Acme", "priority": "high", "discovered_from": "test-slug"},
        ]

        with patch.object(sl, 'DATA', tmp_path):
            sl.cmd_write_pending(adds=json.dumps(adds_data), completions=None)

        assert adds_path.exists()
        loaded = yaml.safe_load(adds_path.read_text())
        assert len(loaded) == 1
        assert loaded[0]["name"] == "Jane Doe"

    def test_write_pending_creates_completions(self, tmp_path):
        """write-pending --completions should write .pending-completions.yaml."""
        completions_path = tmp_path / ".pending-completions.yaml"

        with patch.object(sl, 'DATA', tmp_path):
            sl.cmd_write_pending(adds=None, completions=json.dumps(["slug-a", "slug-b"]))

        assert completions_path.exists()
        loaded = yaml.safe_load(completions_path.read_text())
        assert loaded == ["slug-a", "slug-b"]

    def test_write_pending_appends_to_existing(self, tmp_path):
        """If .pending-queue-adds.yaml already exists, new adds should append."""
        adds_path = tmp_path / ".pending-queue-adds.yaml"
        existing = [{"name": "Existing", "type": "individual"}]
        adds_path.write_text(yaml.dump(existing))

        new_adds = [{"name": "New Person", "type": "individual"}]
        with patch.object(sl, 'DATA', tmp_path):
            sl.cmd_write_pending(adds=json.dumps(new_adds), completions=None)

        loaded = yaml.safe_load(adds_path.read_text())
        assert len(loaded) == 2
        assert loaded[0]["name"] == "Existing"
        assert loaded[1]["name"] == "New Person"

    def test_write_pending_registered_in_dispatch(self):
        """The write-pending command should be registered in the CLI dispatch table."""
        with open(ROOT / "scripts" / "sl") as f:
            source = f.read()
        assert '"write-pending"' in source or "'write-pending'" in source
