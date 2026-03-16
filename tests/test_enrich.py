"""Tests for the CSV enrichment feature (scripts/sl enrich + build.py enrichment index)."""

import csv
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# ── Import enrich functions from scripts/sl (no .py extension) ──
ROOT = Path(__file__).resolve().parent.parent
_sl_path = ROOT / "scripts" / "sl"
_loader = importlib.machinery.SourceFileLoader("sl", str(_sl_path))
spec = importlib.util.spec_from_loader("sl", _loader, origin=str(_sl_path))
sl = importlib.util.module_from_spec(spec)
sl.__file__ = str(_sl_path)
sys.modules["sl"] = sl
spec.loader.exec_module(sl)


# ── Unit tests for _normalize_name ──

class TestNormalizeName:
    def test_basic(self):
        assert sl._normalize_name("Ron Conway") == "ron conway"

    def test_strip_whitespace(self):
        assert sl._normalize_name("  Jane Smith  ") == "jane smith"

    def test_remove_title_prefix(self):
        assert sl._normalize_name("Dr. Jane Smith") == "jane smith"
        assert sl._normalize_name("Mr. John Doe") == "john doe"
        assert sl._normalize_name("Mrs. Sarah Lee") == "sarah lee"

    def test_remove_suffix(self):
        assert sl._normalize_name("John Doe Jr.") == "john doe"
        assert sl._normalize_name("Robert Smith III") == "robert smith"

    def test_empty(self):
        assert sl._normalize_name("") == ""
        assert sl._normalize_name(None) == ""


# ── Unit tests for _match_value ──

class TestMatchValue:
    @pytest.fixture
    def sample_data(self):
        investors = {
            "ron conway": {
                "name": "Ron Conway", "slug": "ron-conway", "type": "individual",
                "firm": "sv-angel", "stage_focus": ["seed"], "sector_focus": ["fintech"],
                "check_size": "$25K-$100K", "location": "San Francisco, CA",
                "status": "published", "thesis_summary": "Based on 45 investments...",
            },
            "mike maples": {
                "name": "Mike Maples", "slug": "mike-maples", "type": "individual",
                "firm": "floodgate", "stage_focus": ["seed"],
                "status": "published",
            },
        }
        firms = {
            "sequoia capital": {
                "name": "Sequoia Capital", "slug": "sequoia-capital", "type": "firm",
                "stage_focus": ["seed", "series-a"], "status": "published",
            },
        }
        queued = [
            {"name": "Chris Dixon", "type": "individual", "firm": "a16z", "status": "pending"},
        ]
        return investors, firms, queued

    def test_exact_investor_match(self, sample_data):
        investors, firms, queued = sample_data
        match_type, conf, profile, name = sl._match_value("Ron Conway", investors, firms, queued)
        assert match_type == "exact"
        assert conf == 1.0
        assert profile["slug"] == "ron-conway"

    def test_exact_firm_match(self, sample_data):
        investors, firms, queued = sample_data
        match_type, conf, profile, name = sl._match_value("Sequoia Capital", investors, firms, queued)
        assert match_type == "firm_only"
        assert conf == 1.0
        assert profile["slug"] == "sequoia-capital"

    def test_fuzzy_investor_match(self, sample_data):
        investors, firms, queued = sample_data
        # Misspelled name should still fuzzy match
        match_type, conf, profile, name = sl._match_value("Ron Conwey", investors, firms, queued)
        assert match_type == "fuzzy"
        assert conf >= 0.75
        assert profile["slug"] == "ron-conway"

    def test_no_match(self, sample_data):
        investors, firms, queued = sample_data
        match_type, conf, profile, name = sl._match_value("Completely Unknown Person", investors, firms, queued)
        assert match_type == "none"
        assert conf == 0.0
        assert profile is None

    def test_queued_match(self, sample_data):
        investors, firms, queued = sample_data
        match_type, conf, profile, name = sl._match_value("Chris Dixon", investors, firms, queued)
        assert match_type == "queued"
        assert conf >= 0.80

    def test_empty_value(self, sample_data):
        investors, firms, queued = sample_data
        match_type, conf, profile, name = sl._match_value("", investors, firms, queued)
        assert match_type == "none"

    def test_case_insensitive(self, sample_data):
        investors, firms, queued = sample_data
        match_type, conf, profile, name = sl._match_value("RON CONWAY", investors, firms, queued)
        assert match_type == "exact"


# ── Unit tests for _detect_name_column ──

class TestDetectNameColumn:
    def test_detects_name_column(self):
        investors = {
            "ron conway": {"name": "Ron Conway"},
            "mike maples": {"name": "Mike Maples"},
        }
        firms = {"sequoia capital": {"name": "Sequoia Capital"}}
        rows = [
            {"Name": "Ron Conway", "Email": "ron@svangel.com", "Notes": "seed investor"},
            {"Name": "Mike Maples", "Email": "mike@floodgate.com", "Notes": "floodgate"},
        ]
        name_col, firm_col = sl._detect_name_column(rows, investors, firms)
        assert name_col == "Name"

    def test_detects_firm_column(self):
        investors = {
            "ron conway": {"name": "Ron Conway"},
            "mike maples": {"name": "Mike Maples"},
            "alfred lin": {"name": "Alfred Lin"},
        }
        firms = {
            "sequoia capital": {"name": "Sequoia Capital"},
            "sv angel": {"name": "SV Angel"},
        }
        rows = [
            {"Investor": "Ron Conway", "Firm": "SV Angel", "Stage": "seed"},
            {"Investor": "Mike Maples", "Firm": "Sequoia Capital", "Stage": "series-a"},
            {"Investor": "Alfred Lin", "Firm": "Sequoia Capital", "Stage": "seed"},
        ]
        name_col, firm_col = sl._detect_name_column(rows, investors, firms)
        assert name_col == "Investor"
        assert firm_col == "Firm"

    def test_fallback_heuristic(self):
        investors = {}
        firms = {}
        rows = [
            {"investor_name": "Unknown", "firm_name": "Unknown Fund"},
        ]
        name_col, firm_col = sl._detect_name_column(rows, investors, firms)
        assert name_col == "investor_name"
        assert firm_col == "firm_name"

    def test_empty_rows(self):
        name_col, firm_col = sl._detect_name_column([], {}, {})
        assert name_col is None


# ── Unit tests for _enrich_row ──

class TestEnrichRow:
    def test_enriches_matched_investor(self):
        investors = {
            "ron conway": {
                "name": "Ron Conway", "slug": "ron-conway", "type": "individual",
                "firm": "sv-angel", "stage_focus": ["seed"],
                "sector_focus": ["fintech", "consumer-internet"],
                "check_size": "$25K-$100K", "location": "San Francisco, CA",
                "status": "published", "thesis_summary": "Seed investor...",
                "last_verified_investment": {"date": "2023-06-15", "company": "Acme"},
            },
        }
        row = {"Name": "Ron Conway", "Email": "ron@test.com"}
        result = sl._enrich_row(row, "Name", None, investors, {}, [])
        assert result["seedlist_match"] == "exact"
        assert result["seedlist_confidence"] == 1.0
        assert "ron-conway" in result["seedlist_url"]
        assert result["investor_stage_focus"] == "seed"
        assert result["investor_sector_focus"] == "fintech, consumer-internet"
        assert result["investor_check_size"] == "$25K-$100K"
        assert result["last_active"] == "2023-06-15"

    def test_no_match_returns_empty_enrichment(self):
        row = {"Name": "Nobody", "Email": "no@test.com"}
        result = sl._enrich_row(row, "Name", None, {}, {}, [])
        assert result["seedlist_match"] == "none"
        assert result["seedlist_url"] == ""
        assert result["investor_stage_focus"] == ""

    def test_firm_column_fallback(self):
        firms = {
            "sequoia capital": {
                "name": "Sequoia Capital", "slug": "sequoia-capital", "type": "firm",
                "stage_focus": ["seed", "series-a"], "status": "published",
            },
        }
        row = {"Name": "Unknown Person", "Firm": "Sequoia Capital"}
        result = sl._enrich_row(row, "Name", "Firm", {}, firms, [])
        assert result["seedlist_match"] == "firm_only"
        assert "sequoia-capital" in result["seedlist_url"]


# ── Integration test: full CLI enrich pipeline ──

class TestEnrichCLI:
    @pytest.fixture
    def sample_csv(self, tmp_path):
        csv_path = tmp_path / "input.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Firm", "Email"])
            writer.writerow(["Ron Conway", "SV Angel", "ron@test.com"])
            writer.writerow(["Unknown Person", "Unknown Fund", "who@test.com"])
        return csv_path

    def test_enrich_creates_output_file(self, sample_csv, tmp_path):
        output_path = tmp_path / "output.csv"
        sl.cmd_enrich(str(sample_csv), str(output_path))
        assert output_path.exists()

    def test_enrich_preserves_original_columns(self, sample_csv, tmp_path):
        output_path = tmp_path / "output.csv"
        sl.cmd_enrich(str(sample_csv), str(output_path))
        with open(output_path, newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
        assert "Name" in fields
        assert "Firm" in fields
        assert "Email" in fields

    def test_enrich_adds_enrichment_columns(self, sample_csv, tmp_path):
        output_path = tmp_path / "output.csv"
        sl.cmd_enrich(str(sample_csv), str(output_path))
        with open(output_path, newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
        assert "seedlist_match" in fields
        assert "seedlist_confidence" in fields
        assert "seedlist_url" in fields
        assert "investor_stage_focus" in fields

    def test_enrich_default_output_name(self, sample_csv, tmp_path):
        sl.cmd_enrich(str(sample_csv))
        expected = sample_csv.with_name("input_enriched.csv")
        assert expected.exists()

    def test_enrich_csv_readable_in_dictreader(self, sample_csv, tmp_path):
        output_path = tmp_path / "output.csv"
        sl.cmd_enrich(str(sample_csv), str(output_path))
        with open(output_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        # First row should have a match (Ron Conway is in the real data)
        # Second row should not match


# ── Tests for similarity scoring ──

class TestFindSimilarInvestors:
    @pytest.fixture
    def investor_pool(self):
        """Pool of investors to recommend from."""
        return {
            "alice investor": {
                "name": "Alice Investor", "slug": "alice-investor", "type": "individual",
                "stage_focus": ["seed", "series-a"], "sector_focus": ["fintech", "enterprise"],
                "check_size": "$500K", "location": "SF", "status": "published",
                "thesis_summary": "Fintech and enterprise at seed.",
            },
            "bob venture": {
                "name": "Bob Venture", "slug": "bob-venture", "type": "individual",
                "stage_focus": ["seed"], "sector_focus": ["fintech", "developer-tools"],
                "check_size": "$250K", "location": "NYC", "status": "published",
                "thesis_summary": "Seed fintech and dev tools.",
            },
            "carol growth": {
                "name": "Carol Growth", "slug": "carol-growth", "type": "individual",
                "stage_focus": ["growth", "late-stage"], "sector_focus": ["biotech", "pharma"],
                "check_size": "$10M", "location": "Boston", "status": "published",
                "thesis_summary": "Late stage biotech.",
            },
            "dave seed": {
                "name": "Dave Seed", "slug": "dave-seed", "type": "individual",
                "stage_focus": ["seed"], "sector_focus": ["fintech", "consumer"],
                "check_size": "$100K", "location": "SF", "status": "published",
                "thesis_summary": "Seed fintech consumer.",
            },
        }

    def test_finds_similar_investors(self, investor_pool):
        # Enriched rows that look like seed/fintech investors
        enriched_rows = [
            {
                "seedlist_match": "exact", "seedlist_url": "https://seedlist.com/investors/matched-one.html",
                "investor_stage_focus": "seed", "investor_sector_focus": "fintech, enterprise",
            },
            {
                "seedlist_match": "exact", "seedlist_url": "https://seedlist.com/investors/matched-two.html",
                "investor_stage_focus": "seed, series-a", "investor_sector_focus": "fintech, developer-tools",
            },
        ]
        results = sl._find_similar_investors(enriched_rows, investor_pool)
        # Alice, Bob, Dave should score well (fintech/seed overlap)
        # Carol should NOT appear (biotech/growth is completely different)
        names = [p.get("name") for _, p in results]
        assert "Carol Growth" not in names
        assert len(results) > 0
        # All results should have score >= 0.4
        for score, _ in results:
            assert score >= 0.4

    def test_excludes_already_matched(self, investor_pool):
        enriched_rows = [
            {
                "seedlist_match": "exact",
                "seedlist_url": "https://seedlist.com/investors/alice-investor.html",
                "investor_stage_focus": "seed, series-a",
                "investor_sector_focus": "fintech, enterprise",
            },
            {
                "seedlist_match": "exact",
                "seedlist_url": "https://seedlist.com/investors/bob-venture.html",
                "investor_stage_focus": "seed",
                "investor_sector_focus": "fintech, developer-tools",
            },
        ]
        results = sl._find_similar_investors(enriched_rows, investor_pool)
        slugs = [p.get("slug") for _, p in results]
        assert "alice-investor" not in slugs
        assert "bob-venture" not in slugs

    def test_needs_minimum_matches(self, investor_pool):
        # Only 1 matched row — should return empty (need >= 2)
        enriched_rows = [
            {
                "seedlist_match": "exact",
                "seedlist_url": "https://seedlist.com/investors/someone.html",
                "investor_stage_focus": "seed",
                "investor_sector_focus": "fintech",
            },
        ]
        results = sl._find_similar_investors(enriched_rows, investor_pool)
        assert results == []

    def test_skips_unmatched_rows(self, investor_pool):
        enriched_rows = [
            {"seedlist_match": "none", "investor_stage_focus": "", "investor_sector_focus": ""},
            {"seedlist_match": "queued", "investor_stage_focus": "", "investor_sector_focus": ""},
            {
                "seedlist_match": "exact",
                "seedlist_url": "https://seedlist.com/investors/x.html",
                "investor_stage_focus": "seed",
                "investor_sector_focus": "fintech",
            },
        ]
        # Only 1 real match, so should return empty
        results = sl._find_similar_investors(enriched_rows, investor_pool)
        assert results == []

    def test_results_sorted_by_score(self, investor_pool):
        enriched_rows = [
            {
                "seedlist_match": "exact",
                "seedlist_url": "https://seedlist.com/investors/x.html",
                "investor_stage_focus": "seed",
                "investor_sector_focus": "fintech, enterprise",
            },
            {
                "seedlist_match": "exact",
                "seedlist_url": "https://seedlist.com/investors/y.html",
                "investor_stage_focus": "seed, series-a",
                "investor_sector_focus": "fintech, developer-tools, enterprise",
            },
        ]
        results = sl._find_similar_investors(enriched_rows, investor_pool)
        if len(results) >= 2:
            scores = [s for s, _ in results]
            assert scores == sorted(scores, reverse=True)


# ── Tests for build.py enrichment index ──

class TestEnrichmentIndex:
    def test_build_enrichment_index_structure(self):
        sys.path.insert(0, str(ROOT))
        import build

        investors = [{
            "name": "Test Investor", "slug": "test-investor", "type": "individual",
            "firm": "test-firm", "role": "Partner", "location": "SF",
            "stage_focus": ["seed"], "sector_focus": ["fintech"],
            "check_size": "$100K", "status": "published",
            "last_verified_investment": {"date": "2025-01-01", "company": "Acme"},
            "content": "<h2>Inferred Thesis</h2><p>Invests primarily in seed-stage fintech.</p><h2>Portfolio</h2>",
        }]
        firms = [{
            "name": "Test Firm", "slug": "test-firm", "type": "firm",
            "location": "SF", "stage_focus": ["seed"],
            "sector_focus": ["fintech"], "fund_size": "$100M",
            "status": "published",
        }]

        # Create a temp queue file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("queue:\n- name: Queued Person\n  type: individual\n  status: pending\n")
            queue_path = Path(f.name)

        try:
            index = build.build_enrichment_index(investors, firms, queue_path)

            assert len(index["investors"]) == 1
            assert index["investors"][0]["name"] == "Test Investor"
            assert index["investors"][0]["slug"] == "test-investor"
            assert index["investors"][0]["last_active"] == "2025-01-01"
            assert "fintech" in index["investors"][0]["thesis_summary"]
            assert index["investors"][0]["firm_name"] == "Test Firm"

            assert len(index["firms"]) == 1
            assert index["firms"][0]["name"] == "Test Firm"

            assert len(index["queued"]) == 1
            assert index["queued"][0]["name"] == "Queued Person"
        finally:
            os.unlink(queue_path)

    def test_enrichment_index_json_serializable(self):
        sys.path.insert(0, str(ROOT))
        import build

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("queue: []\n")
            queue_path = Path(f.name)

        try:
            index = build.build_enrichment_index([], [], queue_path)
            # Should not raise
            json.dumps(index)
        finally:
            os.unlink(queue_path)
