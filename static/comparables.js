/* Seedlist Comparable Companies Finder — standalone */

(function () {
  "use strict";

  var compMap = null;       // startup-investor-map.json data
  var enrichIndex = null;   // enrichment-index.json data (for "should have invested")
  var compSelected = [];    // selected startup slugs
  var compLastResults = null;

  // ── Helpers ──

  function escHtml(s) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(s));
    return div.innerHTML;
  }

  // ── Init ──

  var _initDone = false;
  document.addEventListener("DOMContentLoaded", function () {
    if (_initDone) return;
    _initDone = true;

    // Load data files
    fetch("/startup-investor-map.json")
      .then(function (r) { return r.json(); })
      .then(function (data) { compMap = data; })
      .catch(function () { console.error("Failed to load startup-investor map"); });

    fetch("/enrichment-index.json")
      .then(function (r) { return r.json(); })
      .then(function (data) { enrichIndex = data; })
      .catch(function () { console.error("Failed to load enrichment index"); });

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
      var qi = 0;
      for (var ni = 0; ni < n.length && qi < q.length; ni++) {
        if (n[ni] === q[qi]) qi++;
      }
      return qi === q.length;
    }

    function compRenderDropdown(matches) {
      compActiveIdx = -1;
      if (!matches.length) {
        var rawQuery = compInput.value.trim();
        if (rawQuery.length > 1) {
          var issueTitle = encodeURIComponent("Suggestion: " + rawQuery);
          var issueBody = encodeURIComponent("<!-- suggestion -->\nquery: " + rawQuery + "\ntype: startup\nsubmitted: " + new Date().toISOString());
          var issueUrl = "https://github.com/ericries/seedlist/issues/new?title=" + issueTitle + "&body=" + issueBody + "&labels=suggestion";
          compDropdown.innerHTML = '<div class="comp-dropdown-item" style="justify-content:center;">'
            + '<a href="' + issueUrl + '" target="_blank" class="search-suggest" style="color:var(--color-link);">Suggest we add <strong>' + escHtml(rawQuery) + '</strong> &rarr;</a></div>';
          compDropdown.style.display = "block";
        } else {
          compDropdown.style.display = "none";
        }
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

    document.addEventListener("click", function (e) {
      if (!e.target.closest(".comp-search-wrap")) {
        compDropdown.style.display = "none";
      }
    });

    // ── Find investors ──

    function compRunSearch() {
      if (!compMap || !compSelected.length) return [];

      var investorMap = {};
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

      var results = Object.keys(investorMap).map(function (k) { return investorMap[k]; });
      results.sort(function (a, b) {
        if (b.companies.length !== a.companies.length) return b.companies.length - a.companies.length;
        if (a.has_profile !== b.has_profile) return a.has_profile ? -1 : 1;
        var aMaxYear = Math.max.apply(null, a.years.map(Number).filter(Boolean)) || 0;
        var bMaxYear = Math.max.apply(null, b.years.map(Number).filter(Boolean)) || 0;
        if (bMaxYear !== aMaxYear) return bMaxYear - aMaxYear;
        return a.name.localeCompare(b.name);
      });

      return results;
    }

    function compFindShouldHave(actualInvestorSlugs) {
      if (!enrichIndex || !enrichIndex.investors || !compMap) return [];

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
      if (sectorKeys.length === 0) return [];

      var scored = [];
      enrichIndex.investors.forEach(function (inv) {
        if (actualInvestorSlugs[inv.slug]) return;
        if (inv.status !== "published") return;

        var score = 0;
        var reasons = [];

        var sectorMatch = [];
        (inv.sector_focus || []).forEach(function (s) {
          if (targetSectors[s.toLowerCase()]) {
            sectorMatch.push(s);
            score += 15 * targetSectors[s.toLowerCase()];
          }
        });
        if (sectorMatch.length > 0) reasons.push("Focuses on " + sectorMatch.slice(0, 3).join(", "));

        (inv.stage_focus || []).forEach(function (s) {
          if (targetStages[s.toLowerCase()]) {
            score += 10;
          }
        });

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

    function compRenderResults(results) {
      compLastResults = results;
      var summaryEl = document.getElementById("comp-summary");
      var tiersEl = document.getElementById("comp-tiers");
      var totalComps = compSelected.length;

      if (!results.length) {
        summaryEl.innerHTML = '<h2>No investors found</h2><p>None of the selected companies have investor data in our database.</p>';
        tiersEl.innerHTML = "";
        document.getElementById("comp-download-btn").style.display = "none";
        document.getElementById("comp-section").style.display = "none";
        document.getElementById("comp-results").style.display = "block";
        return;
      }

      summaryEl.innerHTML = '<h2>Found ' + results.length + ' investors across ' + totalComps + ' comparable' + (totalComps !== 1 ? 's' : '') + '</h2>';

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

      // Dynamic cross-link: "Find more investors" pre-filling Find form with comparable sectors
      var compSectors = {};
      compSelected.forEach(function (slug) {
        if (!compMap) return;
        compMap.startups.forEach(function (s) {
          if (s.slug === slug) {
            (s.sector || []).forEach(function (sec) {
              compSectors[sec.toLowerCase()] = true;
            });
          }
        });
      });
      var sectorParams = Object.keys(compSectors).slice(0, 3);
      if (sectorParams.length > 0) {
        var findUrl = "/find.html?sector=" + sectorParams.join(",");
        html += '<div style="text-align:center; margin-top:1.5rem; padding-top:1rem; border-top:1px solid var(--color-border);">';
        html += '<p style="font-size:0.9rem; color:var(--color-muted);">Want more options? ';
        html += '<a href="' + escHtml(findUrl) + '" style="font-weight:600;">Find investors by stage &amp; sector</a>';
        html += ' | <a href="/enrich.html" style="font-weight:600;">Enrich an existing list</a></p>';
        html += '</div>';
      }

      tiersEl.innerHTML = html;
      document.getElementById("comp-download-btn").style.display = "inline-block";
      document.getElementById("comp-section").style.display = "none";
      document.getElementById("comp-results").style.display = "block";
    }

    compFindBtn.addEventListener("click", function () {
      var results = compRunSearch();
      compRenderResults(results);
    });

    // ── CSV download ──

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

    // ── Reset ──

    document.getElementById("comp-reset-btn").addEventListener("click", function () {
      document.getElementById("comp-section").style.display = "block";
      document.getElementById("comp-results").style.display = "none";
      compSelected = [];
      compRenderChips();
      compFindBtn.disabled = true;
      compLastResults = null;
    });
  });
})();
