/* Seedlist Find Investors — client-side scoring and filtering */

(function () {
  "use strict";

  var index = null;
  var lastResults = null;

  // ── Comparable Companies state ──
  var compMap = null;       // startup-investor-map.json data
  var compSelected = [];    // selected startup slugs
  var compLastResults = null;

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
      summaryEl.innerHTML = '<h2>No matching investors found</h2><p>Try broadening your criteria — select more sectors or a different stage.</p>';
      tiersEl.innerHTML = '';
      document.getElementById("find-download-btn").style.display = "none";
      document.getElementById("find-form-section").style.display = "none";
      document.getElementById("comp-section").style.display = "none";
      document.querySelector(".find-divider").style.display = "none";
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

    tiersEl.innerHTML = html;
    document.getElementById("find-download-btn").style.display = "inline-block";
    document.getElementById("find-form-section").style.display = "none";
    document.getElementById("comp-section").style.display = "none";
    document.querySelector(".find-divider").style.display = "none";
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
      document.getElementById("comp-section").style.display = "block";
      document.querySelector(".find-divider").style.display = "block";
      lastResults = null;
    });

    // ── Comparable Companies: init ──

    fetch("/startup-investor-map.json")
      .then(function (r) { return r.json(); })
      .then(function (data) { compMap = data; })
      .catch(function () { console.error("Failed to load startup-investor map"); });

    var compInput = document.getElementById("comp-search");
    var compDropdown = document.getElementById("comp-dropdown");
    var compSelectedEl = document.getElementById("comp-selected");
    var compFindBtn = document.getElementById("comp-find-btn");
    var compActiveIdx = -1;

    function compGetStartups() {
      return compMap ? compMap.startups : [];
    }

    function compFuzzyMatch(query, name) {
      var q = query.toLowerCase();
      var n = name.toLowerCase();
      if (n.indexOf(q) !== -1) return true;
      // Simple fuzzy: check if all chars of query appear in order
      var qi = 0;
      for (var ni = 0; ni < n.length && qi < q.length; ni++) {
        if (n[ni] === q[qi]) qi++;
      }
      return qi === q.length;
    }

    function compRenderDropdown(matches) {
      compActiveIdx = -1;
      if (!matches.length) {
        compDropdown.style.display = "none";
        return;
      }
      var html = "";
      matches.forEach(function (s) {
        var sectorStr = (s.sector || []).join(", ");
        html += '<div class="comp-dropdown-item" data-slug="' + escHtml(s.slug) + '">';
        html += '<div>' + escHtml(s.name) + '</div>';
        if (sectorStr) {
          html += '<div class="comp-item-sector">' + escHtml(sectorStr) + '</div>';
        }
        html += '</div>';
      });
      compDropdown.innerHTML = html;
      compDropdown.style.display = "block";
    }

    function compAddStartup(slug) {
      if (compSelected.length >= 5) return;
      if (compSelected.indexOf(slug) !== -1) return;
      compSelected.push(slug);
      compInput.value = "";
      compDropdown.style.display = "none";
      compRenderChips();
      compFindBtn.disabled = compSelected.length === 0;
    }

    function compRemoveStartup(slug) {
      compSelected = compSelected.filter(function (s) { return s !== slug; });
      compRenderChips();
      compFindBtn.disabled = compSelected.length === 0;
    }

    function compRenderChips() {
      var html = "";
      compSelected.forEach(function (slug) {
        var startup = compGetStartups().find(function (s) { return s.slug === slug; });
        var name = startup ? startup.name : slug;
        html += '<span class="comp-chip">' + escHtml(name);
        html += ' <span class="comp-chip-remove" data-slug="' + escHtml(slug) + '">&times;</span>';
        html += '</span>';
      });
      compSelectedEl.innerHTML = html;

      // Bind remove buttons
      compSelectedEl.querySelectorAll(".comp-chip-remove").forEach(function (btn) {
        btn.addEventListener("click", function () {
          compRemoveStartup(this.getAttribute("data-slug"));
        });
      });
    }

    compInput.addEventListener("input", function () {
      var q = this.value.trim();
      if (q.length < 1 || !compMap) {
        compDropdown.style.display = "none";
        return;
      }
      var matches = compGetStartups().filter(function (s) {
        return compSelected.indexOf(s.slug) === -1 && compFuzzyMatch(q, s.name);
      }).slice(0, 8);
      compRenderDropdown(matches);
    });

    compInput.addEventListener("keydown", function (e) {
      var items = compDropdown.querySelectorAll(".comp-dropdown-item");
      if (!items.length) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        compActiveIdx = Math.min(compActiveIdx + 1, items.length - 1);
        items.forEach(function (el, i) { el.classList.toggle("active", i === compActiveIdx); });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        compActiveIdx = Math.max(compActiveIdx - 1, 0);
        items.forEach(function (el, i) { el.classList.toggle("active", i === compActiveIdx); });
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (compActiveIdx >= 0 && compActiveIdx < items.length) {
          compAddStartup(items[compActiveIdx].getAttribute("data-slug"));
        }
      } else if (e.key === "Escape") {
        compDropdown.style.display = "none";
      }
    });

    compDropdown.addEventListener("click", function (e) {
      var item = e.target.closest(".comp-dropdown-item");
      if (item) {
        compAddStartup(item.getAttribute("data-slug"));
      }
    });

    // Close dropdown on outside click
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".comp-search-wrap")) {
        compDropdown.style.display = "none";
      }
    });

    // ── Comparable Companies: find investors ──

    function compRunSearch() {
      if (!compMap || !compSelected.length) return [];

      // Aggregate investors across all selected startups
      var investorMap = {}; // key: slug+type -> data
      compSelected.forEach(function (startupSlug) {
        var investors = compMap.startup_investors[startupSlug] || [];
        var startup = compGetStartups().find(function (s) { return s.slug === startupSlug; });
        var startupName = startup ? startup.name : startupSlug;

        investors.forEach(function (inv) {
          var key = inv.slug + "|" + inv.type;
          if (!investorMap[key]) {
            investorMap[key] = {
              slug: inv.slug,
              name: inv.name,
              type: inv.type,
              firm: inv.firm,
              has_profile: inv.has_profile,
              companies: [],
              rounds: [],
              years: [],
            };
          }
          investorMap[key].companies.push(startupName);
          investorMap[key].rounds.push(inv.round || "unknown");
          investorMap[key].years.push(inv.year || "");
        });
      });

      // Convert to array and sort
      var results = Object.keys(investorMap).map(function (k) { return investorMap[k]; });
      results.sort(function (a, b) {
        // Primary: count desc
        if (b.companies.length !== a.companies.length) return b.companies.length - a.companies.length;
        // Secondary: has profile
        if (a.has_profile !== b.has_profile) return a.has_profile ? -1 : 1;
        // Tertiary: most recent year
        var aMaxYear = Math.max.apply(null, a.years.map(Number).filter(Boolean)) || 0;
        var bMaxYear = Math.max.apply(null, b.years.map(Number).filter(Boolean)) || 0;
        if (bMaxYear !== aMaxYear) return bMaxYear - aMaxYear;
        // Name
        return a.name.localeCompare(b.name);
      });

      return results;
    }

    function compRenderResults(results) {
      compLastResults = results;
      var summaryEl = document.getElementById("comp-summary");
      var tiersEl = document.getElementById("comp-tiers");
      var totalComps = compSelected.length;

      if (!results.length) {
        summaryEl.innerHTML = '<h2>No investors found</h2><p>None of the selected companies have investor data in our database.</p>';
        tiersEl.innerHTML = "";
        document.getElementById("comp-download-btn").style.display = "none";
        document.getElementById("comp-results").style.display = "block";
        return;
      }

      summaryEl.innerHTML = '<h2>Found ' + results.length + ' investors across ' + totalComps + ' comparable' + (totalComps !== 1 ? 's' : '') + '</h2>';

      // Group by count
      var groups = {};
      results.forEach(function (r) {
        var count = r.companies.length;
        if (!groups[count]) groups[count] = [];
        groups[count].push(r);
      });

      var counts = Object.keys(groups).map(Number).sort(function (a, b) { return b - a; });
      var html = "";
      counts.forEach(function (count) {
        var label;
        if (count === totalComps && totalComps > 1) {
          label = "Backed all " + count + " companies";
        } else if (totalComps === 1) {
          label = "Backed your comparable";
        } else {
          label = "Backed " + count + " of " + totalComps;
        }
        html += '<div class="comp-group-header">' + escHtml(label) + ' (' + groups[count].length + ')</div>';
        groups[count].forEach(function (r) {
          var nameHtml;
          var profileType = r.type === "firm" ? "firms" : "investors";
          if (r.has_profile) {
            nameHtml = '<a class="comp-investor-name" href="/' + profileType + '/' + escHtml(r.slug) + '.html">' + escHtml(r.name) + '</a>';
          } else {
            nameHtml = '<span class="comp-investor-name">' + escHtml(r.name) + '</span>';
          }
          var firmHtml = r.firm ? '<span class="comp-investor-firm">' + escHtml(r.firm) + '</span>' : '';
          var typeTag = r.type === "firm" ? ' <span class="comp-investor-firm">(firm)</span>' : '';

          // Build companies+round detail
          var detailParts = [];
          for (var i = 0; i < r.companies.length; i++) {
            var part = r.companies[i];
            if (r.rounds[i] && r.rounds[i] !== "unknown") {
              part += " (" + r.rounds[i] + ")";
            }
            detailParts.push(part);
          }

          html += '<div class="comp-investor-row">';
          html += '<div>' + nameHtml + typeTag + firmHtml + '</div>';
          html += '<div class="comp-investor-companies">' + escHtml(detailParts.join(", ")) + '</div>';
          html += '</div>';
        });
      });

      // "Should have invested" section
      var actualSlugs = {};
      results.forEach(function (r) { actualSlugs[r.slug] = true; });
      var shouldHave = compFindShouldHave(actualSlugs);
      if (shouldHave.length > 0) {
        html += '<div class="comp-group-header" style="margin-top: 2rem; color: var(--color-accent);">Thesis match — didn\'t invest but should be on your list (' + shouldHave.length + ')</div>';
        html += '<p style="font-size: 0.8rem; color: var(--color-muted); margin-bottom: 0.5rem;">These investors\' stated focus matches your comparables\' sectors and stages, but they weren\'t on the cap table. Worth a pitch.</p>';
        shouldHave.forEach(function (r) {
          var nameHtml = '<a class="comp-investor-name" href="/investors/' + escHtml(r.slug) + '.html">' + escHtml(r.name) + '</a>';
          var firmHtml = r.firm ? '<span class="comp-investor-firm">' + escHtml(r.firm) + '</span>' : '';
          html += '<div class="comp-investor-row">';
          html += '<div>' + nameHtml + firmHtml + '</div>';
          html += '<div class="comp-investor-companies">' + escHtml(r.reason) + '</div>';
          html += '</div>';
        });

        // Add should-have to results for CSV download
        shouldHave.forEach(function (r) {
          compLastResults.push({
            slug: r.slug,
            name: r.name,
            firm: r.firm,
            type: "individual",
            has_profile: true,
            companies: ["(thesis match)"],
            rounds: [r.reason],
          });
        });
      }

      tiersEl.innerHTML = html;
      document.getElementById("comp-download-btn").style.display = "inline-block";
      document.getElementById("find-form-section").style.display = "none";
      document.getElementById("comp-section").style.display = "none";
      document.querySelector(".find-divider").style.display = "none";
      document.getElementById("comp-results").style.display = "block";
    }

    function compFindShouldHave(actualInvestorSlugs) {
      // Find investors who SHOULD have invested based on thesis match
      // but didn't actually invest in any of the selected comparables
      if (!index || !index.investors || !compMap) return [];

      // Aggregate sectors and stages from selected startups
      var targetSectors = {};
      var targetStages = {};
      compSelected.forEach(function (slug) {
        var startup = null;
        compMap.startups.forEach(function (s) { if (s.slug === slug) startup = s; });
        if (!startup) return;
        (startup.sector || []).forEach(function (s) {
          targetSectors[s.toLowerCase()] = (targetSectors[s.toLowerCase()] || 0) + 1;
        });
        var st = startup.stage || "";
        if (st) targetStages[st.toLowerCase()] = (targetStages[st.toLowerCase()] || 0) + 1;
      });

      var sectorKeys = Object.keys(targetSectors);
      var stageKeys = Object.keys(targetStages);
      if (sectorKeys.length === 0) return [];

      // Score each investor from enrichment index
      var scored = [];
      index.investors.forEach(function (inv) {
        // Skip if they actually invested
        if (actualInvestorSlugs[inv.slug]) return;
        // Skip if not published
        if (inv.status !== "published") return;

        var score = 0;
        var reasons = [];

        // Sector overlap
        var sectorMatch = [];
        (inv.sector_focus || []).forEach(function (s) {
          if (targetSectors[s.toLowerCase()]) {
            sectorMatch.push(s);
            score += 15 * targetSectors[s.toLowerCase()];
          }
        });
        if (sectorMatch.length > 0) reasons.push("Focuses on " + sectorMatch.slice(0, 3).join(", "));

        // Stage overlap
        (inv.stage_focus || []).forEach(function (s) {
          if (targetStages[s.toLowerCase()]) {
            score += 10;
          }
        });

        // Recency bonus
        if (inv.last_active) {
          var months = (Date.now() - new Date(inv.last_active)) / (1000 * 60 * 60 * 24 * 30);
          if (months < 12) { score += 10; reasons.push("Active in last year"); }
        }

        if (score >= 25 && sectorMatch.length >= 1) {
          scored.push({
            slug: inv.slug,
            name: inv.name,
            firm: inv.firm_name || inv.firm || "",
            score: score,
            reason: reasons.join("; "),
            has_profile: true,
            type: "individual",
          });
        }
      });

      scored.sort(function (a, b) { return b.score - a.score; });
      return scored.slice(0, 20);
    }

    compFindBtn.addEventListener("click", function () {
      var results = compRunSearch();
      compRenderResults(results);
    });

    // ── Comparable Companies: CSV download ──

    document.getElementById("comp-download-btn").addEventListener("click", function () {
      if (!compLastResults || !compLastResults.length) return;

      var fields = ["Name", "Type", "Firm", "Companies Backed", "Rounds", "Seedlist URL"];
      var rows = compLastResults.map(function (r) {
        var profileType = r.type === "firm" ? "firms" : "investors";
        return {
          "Name": r.name,
          "Type": r.type,
          "Firm": r.firm || "",
          "Companies Backed": r.companies.join("; "),
          "Rounds": r.rounds.join("; "),
          "Seedlist URL": r.has_profile ? "https://seedlist.com/" + profileType + "/" + r.slug + ".html" : "",
        };
      });

      var csv = Papa.unparse({ fields: fields, data: rows });
      var blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "seedlist_comparable_investors.csv";
      a.click();
      URL.revokeObjectURL(url);
    });

    // ── Comparable Companies: reset ──

    document.getElementById("comp-reset-btn").addEventListener("click", function () {
      document.getElementById("find-form-section").style.display = "block";
      document.getElementById("comp-section").style.display = "block";
      document.querySelector(".find-divider").style.display = "block";
      document.getElementById("comp-results").style.display = "none";
      compSelected = [];
      compRenderChips();
      compFindBtn.disabled = true;
      compLastResults = null;
    });
  });
})();
