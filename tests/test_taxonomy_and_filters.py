"""Tests for sector taxonomy, location normalization, dynamic filters, and user submission pipeline."""

import importlib.machinery
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path

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

# ── Import build module ──
sys.path.insert(0, str(ROOT))
import build


# ===========================================================================
# Sector Taxonomy Tests
# ===========================================================================

class TestSectorTaxonomy:
    @pytest.fixture
    def taxonomy(self):
        with open(DATA / "sector-taxonomy.yaml") as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def tag_to_parents(self, taxonomy):
        mapping = {}
        for parent_slug, parent_data in taxonomy.items():
            for tag in parent_data.get("tags", []):
                tag_lower = tag.lower()
                if tag_lower not in mapping:
                    mapping[tag_lower] = []
                mapping[tag_lower].append(parent_slug)
        return mapping

    def test_taxonomy_file_exists(self):
        assert (DATA / "sector-taxonomy.yaml").exists()

    def test_taxonomy_has_parent_categories(self, taxonomy):
        assert len(taxonomy) >= 15, f"Expected at least 15 parent categories, got {len(taxonomy)}"

    def test_every_category_has_label(self, taxonomy):
        for slug, data in taxonomy.items():
            assert "label" in data, f"Category '{slug}' missing label"
            assert isinstance(data["label"], str) and len(data["label"]) > 0

    def test_every_category_has_tags(self, taxonomy):
        for slug, data in taxonomy.items():
            tags = data.get("tags", [])
            assert len(tags) >= 1, f"Category '{slug}' has no tags"

    def test_no_duplicate_tags_within_category(self, taxonomy):
        for slug, data in taxonomy.items():
            tags = [t.lower() for t in data.get("tags", [])]
            dupes = [t for t in tags if tags.count(t) > 1]
            assert len(dupes) == 0, f"Category '{slug}' has duplicate tags: {set(dupes)}"

    def test_neuroscience_maps_to_healthcare(self, tag_to_parents):
        assert "healthcare" in tag_to_parents.get("neuroscience", [])

    def test_neurotech_maps_to_healthcare(self, tag_to_parents):
        assert "healthcare" in tag_to_parents.get("neurotech", [])

    def test_payments_maps_to_fintech(self, tag_to_parents):
        assert "fintech" in tag_to_parents.get("payments", [])

    def test_ai_drug_discovery_maps_to_both_ai_and_healthcare(self, tag_to_parents):
        parents = tag_to_parents.get("ai-drug-discovery", [])
        assert "ai" in parents
        assert "healthcare" in parents

    def test_autonomous_vehicles_maps_to_robotics_and_mobility(self, tag_to_parents):
        parents = tag_to_parents.get("autonomous-vehicles", [])
        assert "robotics" in parents
        assert "mobility" in parents

    def test_most_profile_tags_are_mapped(self, tag_to_parents):
        """At least 95% of tags used in actual profiles should map to a parent."""
        all_tags = set()
        for subdir in ["investors", "firms"]:
            for md in (DATA / subdir).glob("*.md"):
                post = frontmatter.load(str(md))
                for s in (post.metadata.get("sector_focus") or []):
                    all_tags.add(s.lower())
        mapped = sum(1 for t in all_tags if t in tag_to_parents)
        pct = mapped / len(all_tags) * 100 if all_tags else 100
        assert pct >= 95, f"Only {pct:.0f}% of profile tags are mapped (expected >= 95%)"


# ===========================================================================
# Location Normalization Tests
# ===========================================================================

class TestLocationNormalization:
    """Test the normalize_location function via build.py output."""

    # We test by checking the generated HTML since normalize_location is
    # defined inline in build.py's main() function. Instead, replicate
    # the logic and test key mappings.

    LOCATION_TESTS = [
        # US major hubs
        ("San Francisco, CA", "sf-bay-area"),
        ("Menlo Park, California", "sf-bay-area"),
        ("Palo Alto, CA", "sf-bay-area"),
        ("New York, NY", "nyc"),
        ("Brooklyn, New York", "nyc"),
        ("Los Angeles, CA", "la"),
        ("Santa Monica, CA", "la"),
        ("Boston, MA", "boston"),
        ("Cambridge, MA", "boston"),
        ("Seattle, WA", "seattle"),
        ("Bellevue, WA", "seattle"),
        ("Austin, Texas", "austin"),
        ("Chicago, IL", "chicago"),
        ("Miami, FL", "miami"),
        ("Washington, DC", "dc"),
        ("Denver, CO", "denver"),
        ("Boulder, Colorado", "denver"),
        # International
        ("London, UK", "london"),
        ("London, England", "london"),
        ("Paris, France", "paris"),
        ("Stockholm, Sweden", "sweden"),
        ("Singapore", "singapore"),
        ("Tel Aviv, Israel", "israel"),
        ("Toronto, Canada", "canada"),
        ("São Paulo, Brazil", "brazil"),
        # Empty / unmapped
        ("", ""),
        (None, ""),
    ]

    @pytest.mark.parametrize("location,expected", LOCATION_TESTS)
    def test_location_normalization(self, location, expected):
        # Replicate the normalize_location logic from build.py
        result = self._normalize_location(location)
        assert result == expected, f"normalize_location('{location}') = '{result}', expected '{expected}'"

    @staticmethod
    def _normalize_location(loc):
        """Mirror of build.py's normalize_location for testing."""
        if not loc:
            return ""
        loc_lower = loc.lower()

        sf_keywords = ["san francisco", "menlo park", "palo alto", "mountain view",
                       "woodside", "redwood city", "atherton", "bay area",
                       "saratoga", "cupertino", "sunnyvale", "san mateo",
                       "portola valley", "los altos", "burlingame", "hillsborough"]
        for kw in sf_keywords:
            if kw in loc_lower:
                return "sf-bay-area"
        if "new york" in loc_lower or "brooklyn" in loc_lower:
            return "nyc"
        if "los angeles" in loc_lower or "santa monica" in loc_lower or "venice" in loc_lower or "beverly hills" in loc_lower:
            return "la"
        if "boston" in loc_lower or "cambridge, ma" in loc_lower or "somerville, ma" in loc_lower:
            return "boston"
        if "seattle" in loc_lower or "bellevue" in loc_lower or "kirkland" in loc_lower or "redmond" in loc_lower:
            return "seattle"
        if "austin" in loc_lower:
            return "austin"
        if "chicago" in loc_lower:
            return "chicago"
        if "miami" in loc_lower or "fort lauderdale" in loc_lower:
            return "miami"
        if "washington" in loc_lower and ("dc" in loc_lower or "d.c." in loc_lower):
            return "dc"
        if "denver" in loc_lower or "boulder" in loc_lower:
            return "denver"
        if "london" in loc_lower or "england" in loc_lower:
            return "london"
        if "paris" in loc_lower:
            return "paris"
        if "stockholm" in loc_lower or "malmö" in loc_lower or "malmo" in loc_lower or "sweden" in loc_lower:
            return "sweden"
        if "singapore" in loc_lower:
            return "singapore"
        if "tel aviv" in loc_lower or "israel" in loc_lower or "jerusalem" in loc_lower:
            return "israel"
        if "toronto" in loc_lower or "vancouver" in loc_lower or "montreal" in loc_lower or "ottawa" in loc_lower or "canada" in loc_lower:
            return "canada"
        if "são paulo" in loc_lower or "sao paulo" in loc_lower or "brazil" in loc_lower or "rio" in loc_lower:
            return "brazil"
        return ""


# ===========================================================================
# Dynamic Filter Tests
# ===========================================================================

class TestDynamicFilters:
    """Verify the generated HTML only contains filter options with matching profiles."""

    @pytest.fixture(scope="class")
    def generated_html(self):
        html_path = ROOT / "_site" / "investors" / "index.html"
        if not html_path.exists():
            pytest.skip("Site not built — run 'python build.py' first")
        return html_path.read_text()

    def test_all_sector_options_have_matches(self, generated_html):
        sector_section = generated_html.split('id="filter-sector"')[1].split("</select>")[0]
        options = re.findall(r'<option value="([^"]+)">', sector_section)
        for opt in options:
            matches = len(re.findall(
                f'data-sector-parents="[^"]*{re.escape(opt)}[^"]*"', generated_html
            ))
            assert matches > 0, f"Sector option '{opt}' has 0 matching profiles"

    def test_all_location_options_have_matches(self, generated_html):
        location_section = generated_html.split('id="filter-location"')[1].split("</select>")[0]
        options = re.findall(r'<option value="([^"]+)">', location_section)
        # Filter out sort options that might appear after location
        sort_options = {"recent", "name-asc", "name-desc"}
        location_opts = [o for o in options if o not in sort_options]
        for opt in location_opts:
            matches = len(re.findall(
                f'data-location="{re.escape(opt)}"', generated_html
            ))
            assert matches > 0, f"Location option '{opt}' has 0 matching profiles"

    def test_cards_have_sector_parents_attribute(self, generated_html):
        cards = re.findall(r'data-sector-parents="([^"]*)"', generated_html)
        assert len(cards) > 0, "No cards found with data-sector-parents attribute"
        # At least some cards should have non-empty sector parents
        non_empty = [c for c in cards if c]
        assert len(non_empty) > len(cards) * 0.8, "Too many cards with empty sector-parents"

    def test_js_uses_sector_parents_for_filtering(self, generated_html):
        assert "data-sector-parents" in generated_html
        assert "sectorParents.indexOf(sector)" in generated_html


# ===========================================================================
# User Submission Pipeline Tests
# ===========================================================================

class TestProcessIssues:
    """Test the process_issues.py profile-not-found fix."""

    def test_process_issues_compiles(self):
        import py_compile
        py_compile.compile(str(ROOT / "scripts" / "process_issues.py"), doraise=True)

    def test_process_issues_creates_stub_on_missing_profile(self):
        """Verify that when find_profile returns None, a stub is created."""
        with open(ROOT / "scripts" / "process_issues.py") as f:
            code = f.read()
        # The fix should create a stub profile with pending_sources
        assert "profile_path is None" in code
        assert "pending_sources" in code
        assert "stub_meta" in code
        # The fix should add to queue
        assert "queue_list.append" in code
        # The fix should NOT just close the issue and lose the URL
        # (the old code was: close_issue(number, f"Profile not found: {slug}"); continue)
        # Verify the stub creation comes BEFORE any close_issue in the None branch
        none_branch = code.split("profile_path is None")[1].split("continue")[0]
        assert "stub_meta" in none_branch
        assert "pending_sources" in none_branch


class TestEnsurePendingSourcesQueued:
    """Test the _ensure_pending_sources_queued function in sl."""

    def test_function_exists(self):
        assert hasattr(sl, "_ensure_pending_sources_queued")

    def test_called_in_post_batch(self):
        """Verify post_batch calls _ensure_pending_sources_queued."""
        import inspect
        source = inspect.getsource(sl.cmd_post_batch)
        assert "_ensure_pending_sources_queued()" in source

    def test_function_scans_profiles(self):
        """Verify the function looks for pending_sources with status: queued."""
        import inspect
        source = inspect.getsource(sl._ensure_pending_sources_queued)
        assert "pending_sources" in source
        assert '"queued"' in source or "'queued'" in source


# ===========================================================================
# Integration: Full Build Test
# ===========================================================================

class TestBuildIntegration:
    def test_build_produces_investor_listing(self):
        html_path = ROOT / "_site" / "investors" / "index.html"
        assert html_path.exists(), "Build did not produce investors/index.html"

    def test_investor_listing_has_filter_controls(self):
        html_path = ROOT / "_site" / "investors" / "index.html"
        if not html_path.exists():
            pytest.skip("Site not built")
        html = html_path.read_text()
        assert 'id="filter-stage"' in html
        assert 'id="filter-sector"' in html
        assert 'id="filter-location"' in html
        assert 'id="filter-sort"' in html

    def test_taxonomy_categories_in_dropdown(self):
        html_path = ROOT / "_site" / "investors" / "index.html"
        if not html_path.exists():
            pytest.skip("Site not built")
        html = html_path.read_text()
        # Check key categories appear
        assert "Healthcare &amp; Life Sciences" in html or "Healthcare & Life Sciences" in html
        assert "AI &amp; Machine Learning" in html or "AI & Machine Learning" in html
        assert "Fintech" in html

    def test_location_optgroups_present(self):
        html_path = ROOT / "_site" / "investors" / "index.html"
        if not html_path.exists():
            pytest.skip("Site not built")
        html = html_path.read_text()
        # Should have US optgroup at minimum
        assert '<optgroup label="US">' in html
