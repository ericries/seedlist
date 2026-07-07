"""Tests for two regressions:

1. Startup frontmatter with implausible `year:` values (e.g., year: 8090)
   should be flagged by `sl lint` — root cause of the "undated round at top"
   bug where the company name "8090" was mis-parsed as a year.

2. `sl pending-rounds --cleanup` should garbage-collect pending entries
   whose companies already have startup profiles — root cause of the
   "74 pending research entries" backlog where the RSS scraper piles up
   entries that agents have already shipped via broad web-search sweeps.
"""

import importlib.machinery
import importlib.util
import io
import sys
import tempfile
import textwrap
from contextlib import redirect_stdout
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
_sl_path = ROOT / "scripts" / "sl"
_loader = importlib.machinery.SourceFileLoader("sl", str(_sl_path))
spec = importlib.util.spec_from_loader("sl", _loader, origin=str(_sl_path))
sl = importlib.util.module_from_spec(spec)
sl.__file__ = str(_sl_path)
sys.modules["sl"] = sl
spec.loader.exec_module(sl)


# ── Error 1: frontmatter year validation ──

def _write_startup(tmpdir, slug, frontmatter_yaml, body):
    startups = tmpdir / "data" / "startups"
    startups.mkdir(parents=True, exist_ok=True)
    (startups / f"{slug}.md").write_text(f"---\n{frontmatter_yaml}---\n\n{body}\n")


def test_lint_flags_implausible_year_in_startup_frontmatter(tmp_path, monkeypatch):
    """A startup profile with year: 8090 in its firms/investors array
    should fail lint. This is the exact bug that surfaced on 8090 Labs
    where the company name was mis-parsed as a year."""
    monkeypatch.setattr(sl, "DATA", tmp_path / "data")

    _write_startup(
        tmp_path,
        "acme",
        textwrap.dedent("""\
            name: Acme
            slug: acme
            type: startup
            status: published
            last_researched: 2026-07-06
            sector: [ai]
            firms:
              - slug: bad-firm
                round: series-a
                year: 8090
            """),
        textwrap.dedent("""\
            ## About
            Body.

            ## Funding History
            | Date | Round | Amount | Lead | Co-investors |
            |------|-------|--------|------|--------------|
            | 2026-06-29 | Series A | $135M | Bad Firm | — |

            ## What Investors Say
            No quotes.

            ## What Founders Say
            No quotes.

            ## Sources
            No sources.
            """),
    )

    buf = io.StringIO()
    with redirect_stdout(buf), pytest.raises(SystemExit) as exc:
        sl.cmd_lint("acme", no_fetch=True)
    assert exc.value.code == 1, "lint should exit non-zero on frontmatter year error"
    out = buf.getvalue()
    assert "year" in out.lower() and "8090" in out, f"expected year=8090 error, got:\n{out}"


def test_lint_accepts_plausible_year_in_startup_frontmatter(tmp_path, monkeypatch):
    """A well-formed startup profile with year: 2026 should pass lint's
    frontmatter year check (may still warn on other things — we only
    assert the year check does not trigger)."""
    monkeypatch.setattr(sl, "DATA", tmp_path / "data")

    _write_startup(
        tmp_path,
        "acme",
        textwrap.dedent("""\
            name: Acme
            slug: acme
            type: startup
            status: published
            last_researched: 2026-07-06
            sector: [ai]
            firms:
              - slug: bad-firm
                round: series-a
                year: 2026
            """),
        textwrap.dedent("""\
            ## About
            Body.

            ## Funding History
            | Date | Round | Amount | Lead | Co-investors |
            |------|-------|--------|------|--------------|
            | 2026-06-29 | Series A | $135M | Bad Firm | — |

            ## What Investors Say
            No quotes.

            ## What Founders Say
            No quotes.

            ## Sources
            No sources.
            """),
    )

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            sl.cmd_lint("acme", no_fetch=True)
    except SystemExit:
        pass  # may exit non-zero for unrelated reasons; we only check the year check
    out = buf.getvalue()
    assert "year=8090" not in out, "should not flag year=2026 as implausible"
    assert "implausible year" not in out.lower() or "2026" not in out, \
        f"should not flag plausible year, got:\n{out}"


# ── Error 2: pending-rounds cleanup ──

def _write_pending(tmp_path, entries):
    p = tmp_path / "data" / "pending-rounds.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.dump({"pending_rounds": entries}))
    return p


def _write_shipped_startups(tmp_path, slugs):
    startups = tmp_path / "data" / "startups"
    startups.mkdir(parents=True, exist_ok=True)
    for s in slugs:
        (startups / f"{s}.md").write_text(
            f"---\nname: {s}\nslug: {s}\ntype: startup\nstatus: published\n---\n"
        )


def test_pending_rounds_cleanup_removes_shipped_matches(tmp_path, monkeypatch):
    """sl pending-rounds --cleanup should drop pending entries whose
    companies match an existing data/startups/*.md profile. This is the
    root fix for the 74-pending-entries backlog: the scraper piles up
    candidates that agents have already shipped."""
    monkeypatch.setattr(sl, "DATA", tmp_path / "data")
    monkeypatch.setattr(sl, "ROOT", tmp_path)

    _write_shipped_startups(tmp_path, ["stoa", "quantum-systems", "linqalpha"])
    _write_pending(tmp_path, [
        {"title": "Stoa raised $2.4M", "url": "https://example.com/1", "status": "pending"},
        {"title": "Quantum Systems raised $1.2B Series D", "url": "https://ex.com/2", "status": "pending"},
        {"title": "LinqAlpha raised $22M Series A", "url": "https://ex.com/3", "status": "pending"},
        {"title": "GenuinelyNewStartup raised $10M Seed", "url": "https://ex.com/4", "status": "pending"},
    ])

    buf = io.StringIO()
    with redirect_stdout(buf):
        sl.cmd_pending_rounds(cleanup=True)

    with open(tmp_path / "data" / "pending-rounds.yaml") as f:
        data = yaml.safe_load(f)

    remaining = [
        r for r in data["pending_rounds"]
        if r.get("status", "pending") == "pending"
    ]
    remaining_titles = {r["title"] for r in remaining}
    assert remaining_titles == {"GenuinelyNewStartup raised $10M Seed"}, \
        f"expected only genuinely-new entry to survive, got: {remaining_titles}"


def test_pending_rounds_read_only_by_default(tmp_path, monkeypatch):
    """Default `sl pending-rounds` (no --cleanup) should be read-only —
    must not mutate the file. Belt-and-suspenders check that cleanup is
    strictly opt-in so cron firings don't accidentally delete work."""
    monkeypatch.setattr(sl, "DATA", tmp_path / "data")
    monkeypatch.setattr(sl, "ROOT", tmp_path)

    _write_shipped_startups(tmp_path, ["stoa"])
    _write_pending(tmp_path, [
        {"title": "Stoa raised $2.4M", "url": "https://example.com/1", "status": "pending"},
    ])
    before = (tmp_path / "data" / "pending-rounds.yaml").read_text()

    buf = io.StringIO()
    with redirect_stdout(buf):
        sl.cmd_pending_rounds()  # default cleanup=False

    after = (tmp_path / "data" / "pending-rounds.yaml").read_text()
    assert before == after, "default pending-rounds must be read-only"
