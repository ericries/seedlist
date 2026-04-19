/* Seedlist Find Investors — client-side scoring and filtering */

(function () {
  "use strict";

  var index = null;
  var lastResults = null;

  // ── Check size parsing ──

  function parseCheckSize(str) {
    // Parse strings like "$250K-$1M", "$1M-$5M", "$100K", "$5M+" into { min, max } in dollars
    if (!str) return null;
    var s = str.replace(/,/g, "").toLowerCase();
    var numbers = [];
    var re = /\$?([\d.]+)\s*(k|m|b)?/gi;
    var match;
    while ((match = re.exec(s)) !== null) {
      var val = parseFloat(match[1]);
      var unit = (match[2] || "").toLowerCase();
      if (unit === "k") val *= 1000;
      else if (unit === "m") val *= 1000000;
      else if (unit === "b") val *= 1000000000;
      numbers.push(val);
    }
    if (numbers.length === 0) return null;
    if (numbers.length === 1) {
      // Single value — treat as center of range
      if (s.indexOf("+") !== -1) return { min: numbers[0], max: Infinity };
      return { min: numbers[0] * 0.5, max: numbers[0] * 2 };
    }
    return { min: Math.min(numbers[0], numbers[1]), max: Math.max(numbers[0], numbers[1]) };
  }

  function criteriaCheckRange(criteriaVal) {
    // Map the dropdown values to numeric ranges
    var ranges = {
      "lt500k": { min: 0, max: 500000 },
      "500k-2m": { min: 500000, max: 2000000 },
      "2m-5m": { min: 2000000, max: 5000000 },
      "5m+": { min: 5000000, max: Infinity }
    };
    return ranges[criteriaVal] || null;
  }

  function checkSizeOverlap(investorCheckSize, criteriaVal) {
    if (!criteriaVal) return false;
    var invRange = parseCheckSize(investorCheckSize);
    var criRange = criteriaCheckRange(criteriaVal);
    if (!invRange || !criRange) return false;
    // Ranges overlap if one starts before the other ends
    return invRange.min <= criRange.max && criRange.min <= invRange.max;
  }

  // ── Location matching ──

  function matchLocation(investorLocation, criteriaLocation) {
    if (!criteriaLocation || !investorLocation) return false;
    var loc = investorLocation.toLowerCase();

    var sfKeywords = ["san francisco", "menlo park", "palo alto", "mountain view",
      "woodside", "redwood city", "atherton", "bay area", "saratoga", "cupertino",
      "sunnyvale", "san mateo", "portola valley", "los altos", "burlingame",
      "hillsborough"];

    if (criteriaLocation === "sf") {
      for (var i = 0; i < sfKeywords.length; i++) {
        if (loc.indexOf(sfKeywords[i]) !== -1) return true;
      }
      return false;
    }
    if (criteriaLocation === "nyc") {
      return loc.indexOf("new york") !== -1;
    }
    if (criteriaLocation === "other-us") {
      // US but not SF or NYC
      var usCities = ["boston", "cambridge", "los angeles", "chicago", "seattle",
        "austin", "miami", "denver", "washington", "atlanta", "portland",
        "philadelphia", "dallas", "houston", "nashville", "minneapolis",
        "salt lake", "boulder", "pittsburgh", "raleigh", "durham"];
      var stateAbbrevs = /,\s*[a-z]{2}$/;
      var usKeywords = ["california", "texas", "virginia", "maryland", "colorado",
        "massachusetts", "illinois", "georgia", "florida", "oregon", "washington"];
      for (var j = 0; j < usCities.length; j++) {
        if (loc.indexOf(usCities[j]) !== -1) return true;
      }
      for (var k = 0; k < usKeywords.length; k++) {
        if (loc.indexOf(usKeywords[k]) !== -1) return true;
      }
      if (stateAbbrevs.test(loc)) return true;
      return false;
    }
    if (criteriaLocation === "international") {
      // Not US — heuristic: no US state abbreviation or known US city
      var allUs = sfKeywords.concat(["new york", "boston", "los angeles", "chicago",
        "seattle", "austin", "miami", "denver", "washington", "atlanta", "portland"]);
      for (var m = 0; m < allUs.length; m++) {
        if (loc.indexOf(allUs[m]) !== -1) return false;
      }
      // If it has a comma + 2-letter abbreviation, likely US
      if (/,\s*[a-z]{2}$/.test(loc)) return false;
      return true;
    }
    return false;
  }

  // ── Scoring ──

  function scoreInvestor(investor, criteria) {
    var score = 0;
    var reasons = [];

    // Stage match (0-30 points)
    var stages = investor.stage_focus || [];
    var stageMatch = false;
    for (var i = 0; i < stages.length; i++) {
      if (stages[i].toLowerCase() === criteria.stage.toLowerCase()) {
        stageMatch = true;
        break;
      }
    }
    if (stageMatch) {
      score += 30;
      reasons.push("Invests at " + criteria.stage);
    }

    // Sector match (0-40 points) — most important
    var sectorOverlap = [];
    criteria.sectors.forEach(function (s) {
      var sLower = s.toLowerCase();
      for (var j = 0; j < (investor.sector_focus || []).length; j++) {
        if (investor.sector_focus[j].toLowerCase() === sLower) {
          sectorOverlap.push(s);
          break;
        }
      }
    });
    if (sectorOverlap.length > 0) {
      score += Math.min(40, sectorOverlap.length * 15);
      reasons.push("Focus: " + sectorOverlap.join(", "));
    }

    // Check size fit (0-15 points)
    if (criteria.checkSize && checkSizeOverlap(investor.check_size, criteria.checkSize)) {
      score += 15;
      reasons.push("Check size: " + investor.check_size);
    }

    // Recency bonus (0-15 points)
    if (investor.last_active) {
      var lastDate = new Date(investor.last_active);
      if (!isNaN(lastDate.getTime())) {
        var monthsAgo = (Date.now() - lastDate.getTime()) / (1000 * 60 * 60 * 24 * 30);
        if (monthsAgo < 6) {
          score += 15;
          reasons.push("Active in last 6 months");
        } else if (monthsAgo < 12) {
          score += 10;
          reasons.push("Active in last year");
        } else if (monthsAgo < 24) {
          score += 5;
        }
      }
    }

    // Location bonus (0-5 points, not a hard filter but a tiebreaker)
    if (criteria.location && matchLocation(investor.location || "", criteria.location)) {
      score += 5;
      reasons.push("Located in preferred region");
    }

    var tier = 0;
    if (score >= 60) tier = 1;
    else if (score >= 35) tier = 2;
    else if (score >= 15) tier = 3;

    return { score: score, reasons: reasons, tier: tier };
  }

  // ── Run search ──

  function runSearch(criteria) {
    if (!index || !index.investors) return [];

    var results = [];
    index.investors.forEach(function (inv) {
      var result = scoreInvestor(inv, criteria);
      if (result.tier > 0) {
        results.push({
          investor: inv,
          score: result.score,
          reasons: result.reasons,
          tier: result.tier
        });
      }
    });

    // Sort by score descending
    results.sort(function (a, b) { return b.score - a.score; });
    return results;
  }

  // ── Render ──

  function escHtml(s) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(s));
    return div.innerHTML;
  }

  function renderResults(results) {
    lastResults = results;

    var tiersEl = document.getElementById("find-tiers");
    var summaryEl = document.getElementById("find-summary");

    if (results.length === 0) {
      var sectors = getSelectedSectors().join(", ") || "any";
      var stage = document.getElementById("find-stage").value || "any";
      var suggestionQuery = stage + " investor in " + sectors;
      var issueTitle = encodeURIComponent("Suggestion: " + suggestionQuery);
      var issueBody = encodeURIComponent(
        "<!-- suggestion -->\n" +
        "query: " + suggestionQuery + "\n" +
        "submitted: " + new Date().toISOString() + "\n" +
        "page: " + window.location.href + "\n\n" +
        "**Know a specific investor or firm?** (name + firm)\n\n\n" +
        "**Link** (website, Crunchbase, LinkedIn, etc.)\n\n\n" +
        "**Any other context?** (e.g. what they invest in, how you found them)\n\n"
      );
      var issueUrl = "https://github.com/ericries/seedlist/issues/new?title=" + issueTitle + "&body=" + issueBody + "&labels=suggestion";
      summaryEl.innerHTML = '<h2>No matching investors found</h2><p>Try broadening your criteria — select more sectors or a different stage.</p>'
        + '<p><a href="' + issueUrl + '" target="_blank" class="search-suggest">Suggest we add coverage for this &rarr;</a></p>';
      tiersEl.innerHTML = '';
      document.getElementById("find-download-btn").style.display = "none";
      document.getElementById("find-form-section").style.display = "none";
      document.getElementById("find-results").style.display = "block";
      return;
    }

    // Group by tier
    var tiers = { 1: [], 2: [], 3: [] };
    results.forEach(function (r) { tiers[r.tier].push(r); });

    var tierCount = 0;
    if (tiers[1].length) tierCount++;
    if (tiers[2].length) tierCount++;
    if (tiers[3].length) tierCount++;

    summaryEl.innerHTML = '<h2>Found ' + results.length + ' investors across ' + tierCount + ' tier' + (tierCount !== 1 ? 's' : '') + '</h2>';

    var tierLabels = {
      1: "Strong fit",
      2: "Worth a conversation",
      3: "Stretch but possible"
    };

    var html = "";
    [1, 2, 3].forEach(function (t) {
      if (!tiers[t].length) return;
      html += '<div class="tier-section tier-' + t + '">';
      html += '<div class="tier-header">Tier ' + t + ': ' + tierLabels[t] + ' (' + tiers[t].length + ')</div>';
      html += '<div class="tier-investors">';
      tiers[t].forEach(function (r) {
        var inv = r.investor;
        var url = "/investors/" + escHtml(inv.slug) + ".html";
        var firmDisplay = inv.firm_name || inv.firm || "";
        html += '<div class="investor-result">';
        html += '<a class="investor-result-name" href="' + url + '">' + escHtml(inv.name) + '</a>';
        if (firmDisplay) {
          html += '<div class="investor-result-firm">' + escHtml(firmDisplay);
          if (inv.role) html += ' &middot; ' + escHtml(inv.role);
          html += '</div>';
        }
        html += '<div class="fit-reason">';
        r.reasons.forEach(function (reason) {
          html += '<span>' + escHtml(reason) + '.</span> ';
        });
        if (inv.last_active) {
          html += '<span>Last active: ' + escHtml(inv.last_active) + '.</span>';
        }
        html += '</div>';
        html += '</div>';
      });
      html += '</div></div>';
    });

    // Dynamic cross-links
    html += '<div style="text-align:center; margin-top:1.5rem; padding-top:1rem; border-top:1px solid var(--color-border);">';
    html += '<p style="font-size:0.9rem; color:var(--color-muted);">Know companies similar to yours? ';
    html += '<a href="/comparables.html" style="font-weight:600;">Find their investors</a>';
    html += ' | <a href="/enrich.html" style="font-weight:600;">Enrich an existing list</a></p>';
    html += '</div>';

    tiersEl.innerHTML = html;
    document.getElementById("find-download-btn").style.display = "inline-block";
    document.getElementById("find-form-section").style.display = "none";
    document.getElementById("find-results").style.display = "block";
  }

  // ── CSV download ──

  function downloadCSV() {
    if (!lastResults || !lastResults.length) return;

    var fields = ["Tier", "Name", "Firm", "Why", "Stage Focus", "Sector Focus",
      "Check Size", "Last Active", "Location", "Seedlist URL"];

    var rows = lastResults.map(function (r) {
      var inv = r.investor;
      return {
        "Tier": r.tier,
        "Name": inv.name,
        "Firm": inv.firm_name || inv.firm || "",
        "Why": r.reasons.join(". "),
        "Stage Focus": (inv.stage_focus || []).join(", "),
        "Sector Focus": (inv.sector_focus || []).join(", "),
        "Check Size": inv.check_size || "",
        "Last Active": inv.last_active || "",
        "Location": inv.location || "",
        "Seedlist URL": "https://seedlist.com/investors/" + inv.slug + ".html"
      };
    });

    var csv = Papa.unparse({ fields: fields, data: rows });
    var blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "seedlist_investor_targets.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Sector checkbox limit ──

  function enforceSectorLimit() {
    var boxes = document.querySelectorAll('#sector-checkboxes input[type="checkbox"]');
    var checked = 0;
    boxes.forEach(function (box) { if (box.checked) checked++; });
    document.getElementById("sector-count").textContent = String(checked);

    boxes.forEach(function (box) {
      var label = box.parentElement;
      if (!box.checked && checked >= 3) {
        box.disabled = true;
        label.classList.add("disabled");
      } else {
        box.disabled = false;
        label.classList.remove("disabled");
      }
    });
  }

  // ── Init ──

  var _initDone = false;
  document.addEventListener("DOMContentLoaded", function () {
    if (_initDone) return;
    _initDone = true;

    // Load enrichment index
    fetch("/enrichment-index.json")
      .then(function (r) { return r.json(); })
      .then(function (data) { index = data; })
      .catch(function () { console.error("Failed to load enrichment index"); });

    // Sector checkbox limit
    var sectorBoxes = document.querySelectorAll('#sector-checkboxes input[type="checkbox"]');
    sectorBoxes.forEach(function (box) {
      box.addEventListener("change", enforceSectorLimit);
    });

    // Pre-fill from URL params (e.g., from comparables cross-link)
    var params = new URLSearchParams(window.location.search);
    if (params.get("stage")) {
      var stageEl = document.getElementById("find-stage");
      if (stageEl) stageEl.value = params.get("stage");
    }
    if (params.get("sector")) {
      var prefilledSectors = params.get("sector").split(",");
      sectorBoxes.forEach(function (box) {
        if (prefilledSectors.indexOf(box.value) !== -1 || prefilledSectors.indexOf(box.value.toLowerCase()) !== -1) {
          box.checked = true;
        }
      });
      enforceSectorLimit();
    }
    if (params.get("check")) {
      var checkEl = document.getElementById("find-check-size");
      if (checkEl) checkEl.value = params.get("check");
    }

    // Form submit
    document.getElementById("find-form").addEventListener("submit", function (e) {
      e.preventDefault();

      var stage = document.getElementById("find-stage").value;
      if (!stage) { alert("Please select a stage."); return; }

      var sectors = [];
      sectorBoxes.forEach(function (box) {
        if (box.checked) sectors.push(box.value);
      });
      if (sectors.length === 0) { alert("Please select at least one sector."); return; }

      var checkSize = document.getElementById("find-check-size").value;
      var location = document.getElementById("find-location").value;

      var criteria = {
        stage: stage,
        sectors: sectors,
        checkSize: checkSize,
        location: location
      };

      var results = runSearch(criteria);
      renderResults(results);
    });

    // Download
    document.getElementById("find-download-btn").addEventListener("click", downloadCSV);

    // Reset
    document.getElementById("find-reset-btn").addEventListener("click", function () {
      document.getElementById("find-form-section").style.display = "block";
      document.getElementById("find-results").style.display = "none";
      lastResults = null;
    });

  });
})();
