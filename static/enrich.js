/* Seedlist CSV Enrichment — client-side matching */

(function () {
  "use strict";

  var index = null;
  var enrichedRows = null;
  var enrichedFields = null;
  var recommendedRows = [];
  var savedRecCount = "0";

  // ── Levenshtein / fuzzy matching ──

  function normalize(name) {
    if (!name) return "";
    var s = name.trim().toLowerCase();
    ["dr. ", "dr ", "mr. ", "mr ", "ms. ", "ms ", "mrs. ", "mrs "].forEach(function (p) {
      if (s.indexOf(p) === 0) s = s.slice(p.length);
    });
    [" jr.", " jr", " sr.", " sr", " iii", " ii", " iv", " phd", " md"].forEach(function (suf) {
      if (s.length > suf.length && s.slice(-suf.length) === suf) s = s.slice(0, -suf.length);
    });
    return s.trim();
  }

  function similarity(a, b) {
    if (a === b) return 1;
    if (!a || !b) return 0;
    // SequenceMatcher-like ratio using longest common subsequence
    var longer = a.length >= b.length ? a : b;
    var shorter = a.length < b.length ? a : b;
    if (longer.length === 0) return 1;
    return (longer.length - editDistance(longer, shorter)) / longer.length;
  }

  function editDistance(a, b) {
    var matrix = [];
    for (var i = 0; i <= b.length; i++) matrix[i] = [i];
    for (var j = 0; j <= a.length; j++) matrix[0][j] = j;
    for (var i = 1; i <= b.length; i++) {
      for (var j = 1; j <= a.length; j++) {
        if (b[i - 1] === a[j - 1]) {
          matrix[i][j] = matrix[i - 1][j - 1];
        } else {
          matrix[i][j] = Math.min(
            matrix[i - 1][j - 1] + 1,
            matrix[i][j - 1] + 1,
            matrix[i - 1][j] + 1
          );
        }
      }
    }
    return matrix[b.length][a.length];
  }

  function looksLikeName(value) {
    if (!value || typeof value !== 'string') return false;
    var trimmed = value.trim();
    if (trimmed.length < 3 || trimmed.length > 80) return false;
    // Must have at least 2 words (first + last name)
    var words = trimmed.split(/\s+/);
    if (words.length < 2) return false;
    // Reject if it looks like an email
    if (trimmed.indexOf('@') !== -1) return false;
    // Reject if it's mostly numbers
    if (/^\d+$/.test(trimmed.replace(/\s/g, ''))) return false;
    // Reject common injection patterns
    if (/[<>;{}|\\]/.test(trimmed)) return false;
    return true;
  }

  // ── Build lookup tables from index ──

  var investorsByName = {};
  var firmsByName = {};
  var queuedNames = [];

  function buildLookups() {
    if (!index) return;
    index.investors.forEach(function (inv) {
      investorsByName[normalize(inv.name)] = inv;
    });
    index.firms.forEach(function (f) {
      firmsByName[normalize(f.name)] = f;
    });
    (index.queued || []).forEach(function (q) {
      queuedNames.push(normalize(q.name));
    });
  }

  // ── Match a single value ──

  function matchValue(value) {
    var norm = normalize(value);
    if (!norm) return { type: "none", confidence: 0, profile: null };

    // Exact investor
    if (investorsByName[norm]) {
      return { type: "exact", confidence: 1.0, profile: investorsByName[norm], kind: "investor" };
    }
    // Exact firm
    if (firmsByName[norm]) {
      return { type: "firm_only", confidence: 1.0, profile: firmsByName[norm], kind: "firm" };
    }

    // Fuzzy match
    var bestScore = 0, bestKey = null, bestPool = null, bestKind = "";
    var pools = [
      { pool: investorsByName, kind: "investor" },
      { pool: firmsByName, kind: "firm" }
    ];
    pools.forEach(function (p) {
      Object.keys(p.pool).forEach(function (key) {
        var score = similarity(norm, key);
        if (score > bestScore) {
          bestScore = score;
          bestKey = key;
          bestPool = p.pool;
          bestKind = p.kind;
        }
      });
    });

    if (bestScore >= 0.75 && bestPool) {
      var mtype = bestKind === "investor" ? "fuzzy" : "firm_only";
      return { type: mtype, confidence: Math.round(bestScore * 100) / 100, profile: bestPool[bestKey], kind: bestKind };
    }

    // Check queue
    for (var i = 0; i < queuedNames.length; i++) {
      if (similarity(norm, queuedNames[i]) >= 0.80) {
        return { type: "queued", confidence: Math.round(similarity(norm, queuedNames[i]) * 100) / 100, profile: null };
      }
    }

    return { type: "none", confidence: 0, profile: null };
  }

  // ── Detect name column ──

  function detectNameColumn(rows, headers) {
    if (!rows.length || !headers.length) return { nameCol: headers[0] || null, firmCol: null };

    var sample = rows.slice(0, Math.min(20, rows.length));
    var scores = {};

    headers.forEach(function (col) {
      var matches = 0;
      sample.forEach(function (row) {
        var val = normalize(row[col] || "");
        if (!val) return;
        if (investorsByName[val] || firmsByName[val]) {
          matches++;
        } else {
          // Quick fuzzy
          var found = false;
          [investorsByName, firmsByName].forEach(function (pool) {
            if (found) return;
            Object.keys(pool).forEach(function (key) {
              if (found) return;
              if (similarity(val, key) >= 0.80) { matches++; found = true; }
            });
          });
        }
      });
      scores[col] = matches;
    });

    var sorted = headers.slice().sort(function (a, b) { return (scores[b] || 0) - (scores[a] || 0); });
    var nameCol = (scores[sorted[0]] || 0) > 0 ? sorted[0] : null;
    var firmCol = null;

    // Check for firm column
    if (nameCol && sorted.length > 1 && (scores[sorted[1]] || 0) > 0) {
      var candidate = sorted[1];
      var firmMatches = 0;
      sample.forEach(function (row) {
        var val = normalize(row[candidate] || "");
        if (val && firmsByName[val]) firmMatches++;
      });
      if (firmMatches > 0) firmCol = candidate;
    }

    // Heuristic fallback
    if (!nameCol) {
      var nameKws = ["investor", "name", "contact", "person", "who"];
      headers.forEach(function (col) {
        if (nameCol) return;
        var lc = col.toLowerCase();
        nameKws.forEach(function (kw) { if (lc.indexOf(kw) !== -1) nameCol = col; });
      });
      if (!nameCol) nameCol = headers[0];
    }
    if (!firmCol) {
      var firmKws = ["firm", "fund", "company", "organization", "org", "vc"];
      headers.forEach(function (col) {
        if (col === nameCol || firmCol) return;
        var lc = col.toLowerCase();
        firmKws.forEach(function (kw) { if (lc.indexOf(kw) !== -1) firmCol = col; });
      });
    }

    return { nameCol: nameCol, firmCol: firmCol };
  }

  // ── Enrich rows ──

  function enrichRows(rows, headers) {
    var det = detectNameColumn(rows, headers);
    var nameCol = det.nameCol;
    var firmCol = det.firmCol;

    var addedFields = [
      "seedlist_match", "seedlist_confidence", "seedlist_url", "seedlist_status",
      "investor_stage_focus", "investor_sector_focus", "investor_check_size",
      "investor_location", "firm_name", "last_active", "inferred_thesis_summary"
    ];

    var stats = { exact: 0, fuzzy: 0, firm_only: 0, queued: 0, none: 0 };
    var result = [];

    rows.forEach(function (row) {
      var m = matchValue(row[nameCol] || "");

      // Try firm column if no match
      if (m.type === "none" && firmCol) {
        var fm = matchValue(row[firmCol] || "");
        if (fm.type !== "none") {
          m = fm;
          m.type = "firm_only";
        }
      }

      stats[m.type] = (stats[m.type] || 0) + 1;
      var enriched = {};
      // Copy original
      headers.forEach(function (h) { enriched[h] = row[h] || ""; });

      enriched.seedlist_match = m.type;
      enriched.seedlist_confidence = m.confidence;
      enriched.seedlist_url = "";
      enriched.seedlist_status = "";
      enriched.investor_stage_focus = "";
      enriched.investor_sector_focus = "";
      enriched.investor_check_size = "";
      enriched.investor_location = "";
      enriched.firm_name = "";
      enriched.last_active = "";
      enriched.inferred_thesis_summary = "";

      if (m.profile) {
        var p = m.profile;
        var slug = p.slug || "";
        if (m.kind === "investor") {
          enriched.seedlist_url = "https://seedlist.com/investors/" + slug + ".html";
        } else {
          enriched.seedlist_url = "https://seedlist.com/firms/" + slug + ".html";
        }
        enriched.seedlist_status = p.status || "";
        enriched.investor_stage_focus = (p.stage_focus || []).join(", ");
        enriched.investor_sector_focus = (p.sector_focus || []).join(", ");
        enriched.investor_check_size = p.check_size || p.fund_size || "";
        enriched.investor_location = p.location || "";
        enriched.firm_name = p.firm_name || p.name || "";
        enriched.last_active = p.last_active || "";
        enriched.inferred_thesis_summary = p.thesis_summary || "";
      } else if (m.type === "queued") {
        enriched.seedlist_status = "queued";
      }

      result.push(enriched);
    });

    return { rows: result, fields: headers.concat(addedFields), stats: stats, nameCol: nameCol };
  }

  // ── Similarity scoring ──

  function buildTargetProfile(enrichedRows) {
    // Aggregate stage/sector frequencies from matched investors
    var stageCounts = {};
    var sectorCounts = {};
    var matchedSlugs = {};
    var matchedCount = 0;

    enrichedRows.forEach(function (row) {
      if (row.seedlist_match === "none" || row.seedlist_match === "queued") return;
      matchedCount++;
      // Track slugs to exclude from recommendations
      if (row.seedlist_url) {
        var slug = row.seedlist_url.replace(/.*\//, "").replace(".html", "");
        matchedSlugs[slug] = true;
      }
      (row.investor_stage_focus || "").split(", ").forEach(function (s) {
        s = s.trim();
        if (s) stageCounts[s] = (stageCounts[s] || 0) + 1;
      });
      (row.investor_sector_focus || "").split(", ").forEach(function (s) {
        s = s.trim();
        if (s) sectorCounts[s] = (sectorCounts[s] || 0) + 1;
      });
    });

    if (matchedCount === 0) return null;

    // Normalize to weights (0-1)
    var stageWeights = {};
    var sectorWeights = {};
    Object.keys(stageCounts).forEach(function (k) {
      stageWeights[k] = stageCounts[k] / matchedCount;
    });
    Object.keys(sectorCounts).forEach(function (k) {
      sectorWeights[k] = sectorCounts[k] / matchedCount;
    });

    return {
      stageWeights: stageWeights,
      sectorWeights: sectorWeights,
      matchedSlugs: matchedSlugs,
      matchedCount: matchedCount
    };
  }

  function scoreInvestor(inv, profile) {
    // Weighted Jaccard: how well does this investor's focus overlap
    // with the frequency-weighted target profile?

    // Stage score: sum of target weights for stages the investor covers
    var stageScore = 0;
    var stageTotalWeight = 0;
    Object.keys(profile.stageWeights).forEach(function (s) {
      stageTotalWeight += profile.stageWeights[s];
      if ((inv.stage_focus || []).indexOf(s) !== -1) {
        stageScore += profile.stageWeights[s];
      }
    });
    if (stageTotalWeight > 0) stageScore /= stageTotalWeight;

    // Sector score: same approach
    var sectorScore = 0;
    var sectorTotalWeight = 0;
    Object.keys(profile.sectorWeights).forEach(function (s) {
      sectorTotalWeight += profile.sectorWeights[s];
      if ((inv.sector_focus || []).indexOf(s) !== -1) {
        sectorScore += profile.sectorWeights[s];
      }
    });
    if (sectorTotalWeight > 0) sectorScore /= sectorTotalWeight;

    // Combined: sector matters more than stage (more differentiating)
    return 0.35 * stageScore + 0.65 * sectorScore;
  }

  function findSimilarInvestors(enrichedRows) {
    if (!index || !index.investors) return [];

    var profile = buildTargetProfile(enrichedRows);
    if (!profile || profile.matchedCount < 2) return [];

    // Also exclude investors matched by name (even if different slug format)
    var matchedNames = {};
    enrichedRows.forEach(function (row) {
      if (row.seedlist_match !== "none" && row.seedlist_match !== "queued") {
        // Track firm_name too for firm_only matches
        if (row.firm_name) matchedNames[normalize(row.firm_name)] = true;
      }
    });

    var scored = [];
    index.investors.forEach(function (inv) {
      // Skip already-on-list investors
      if (profile.matchedSlugs[inv.slug]) return;
      if (matchedNames[normalize(inv.name)]) return;

      var score = scoreInvestor(inv, profile);
      if (score >= 0.4) {
        scored.push({ investor: inv, score: score });
      }
    });

    // Sort by score descending, take only strong matches
    scored.sort(function (a, b) { return b.score - a.score; });

    // Dynamic cutoff: take investors until score drops below 60% of the top score
    if (scored.length === 0) return [];
    var topScore = scored[0].score;
    var cutoff = topScore * 0.6;
    var results = [];
    for (var i = 0; i < scored.length && i < 20; i++) {
      if (scored[i].score < cutoff) break;
      results.push(scored[i]);
    }

    return results;
  }

  function recommendationToRow(rec, nameCol, fields) {
    var inv = rec.investor;
    var row = {};
    fields.forEach(function (f) { row[f] = ""; });
    row[nameCol] = inv.name;
    row.seedlist_match = "recommended";
    row.seedlist_confidence = Math.round(rec.score * 100) / 100;
    row.seedlist_url = "https://seedlist.com/investors/" + inv.slug + ".html";
    row.seedlist_status = inv.status || "";
    row.investor_stage_focus = (inv.stage_focus || []).join(", ");
    row.investor_sector_focus = (inv.sector_focus || []).join(", ");
    row.investor_check_size = inv.check_size || "";
    row.investor_location = inv.location || "";
    row.firm_name = inv.firm_name || "";
    row.last_active = inv.last_active || "";
    row.inferred_thesis_summary = inv.thesis_summary || "";
    return row;
  }

  // ── Render preview ──

  function renderPreview(data) {
    var statsEl = document.getElementById("enrich-stats");
    var total = data.rows.length;
    var matched = data.stats.exact + data.stats.fuzzy + data.stats.firm_only;
    var pct = total > 0 ? Math.round(100 * matched / total) : 0;

    statsEl.innerHTML =
      '<div class="stat-item stat-exact"><div class="stat-number">' + data.stats.exact + '</div><div class="stat-label">Exact</div></div>' +
      '<div class="stat-item stat-fuzzy"><div class="stat-number">' + data.stats.fuzzy + '</div><div class="stat-label">Fuzzy</div></div>' +
      '<div class="stat-item stat-firm"><div class="stat-number">' + data.stats.firm_only + '</div><div class="stat-label">Firm only</div></div>' +
      '<div class="stat-item stat-none"><div class="stat-number">' + data.stats.none + '</div><div class="stat-label">No match</div></div>' +
      '<div class="stat-item"><div class="stat-number">' + pct + '%</div><div class="stat-label">Match rate</div></div>';

    // Show subset of columns in preview
    var previewCols = [data.nameCol, "seedlist_match", "seedlist_confidence", "seedlist_url",
      "investor_stage_focus", "investor_sector_focus", "investor_check_size"];

    var thead = document.getElementById("enrich-thead");
    thead.innerHTML = "<tr>" + previewCols.map(function (c) { return "<th>" + escHtml(c) + "</th>"; }).join("") + "</tr>";

    var tbody = document.getElementById("enrich-tbody");
    var previewRows = data.rows.slice(0, 50);
    tbody.innerHTML = previewRows.map(function (row) {
      return "<tr>" + previewCols.map(function (c) {
        var val = row[c] != null ? String(row[c]) : "";
        var cls = "";
        if (c === "seedlist_match") cls = ' class="match-' + val + '"';
        if (c === "seedlist_url" && val) {
          return '<td><a href="' + escHtml(val) + '" target="_blank">view</a></td>';
        }
        return "<td" + cls + ">" + escHtml(val) + "</td>";
      }).join("") + "</tr>";
    }).join("");

    if (data.rows.length > 50) {
      tbody.innerHTML += '<tr><td colspan="' + previewCols.length + '" style="text-align:center;color:var(--color-muted);">...and ' + (data.rows.length - 50) + ' more rows (all included in download)</td></tr>';
    }

    // Compute and render recommendations
    var recs = findSimilarInvestors(data.rows);
    recommendedRows = [];
    var recToggle = document.getElementById("rec-toggle");
    var recSection = document.getElementById("rec-section");
    var recCount = document.getElementById("rec-count");
    var recBody = document.getElementById("rec-tbody");

    if (recs.length > 0) {
      recommendedRows = recs.map(function (r) {
        return recommendationToRow(r, data.nameCol, data.fields);
      });

      savedRecCount = String(recs.length);
      recCount.textContent = savedRecCount;
      recToggle.style.display = "inline-block";

      var recHead = document.getElementById("rec-thead");
      recHead.innerHTML = "<tr>" + previewCols.map(function (c) { return "<th>" + escHtml(c) + "</th>"; }).join("") + "</tr>";

      recBody.innerHTML = recs.map(function (rec) {
        var row = recommendationToRow(rec, data.nameCol, data.fields);
        return '<tr class="rec-row">' + previewCols.map(function (c) {
          var val = row[c] != null ? String(row[c]) : "";
          var cls = "";
          if (c === "seedlist_match") cls = ' class="match-recommended"';
          if (c === "seedlist_url" && val) {
            return '<td><a href="' + escHtml(val) + '" target="_blank">view</a></td>';
          }
          return "<td" + cls + ">" + escHtml(val) + "</td>";
        }).join("") + "</tr>";
      }).join("");
    } else {
      recToggle.style.display = "none";
      recSection.style.display = "none";
    }

    // Render unmatched candidates
    var unmatchedSection = document.getElementById("unmatched-section");
    var unmatchedBody = document.getElementById("unmatched-tbody");
    if (unmatchedSection && unmatchedBody) {
      var unmatched = [];
      data.rows.forEach(function (row) {
        if (row.seedlist_match !== "none") return;
        var name = row[data.nameCol] || "";
        if (!looksLikeName(name)) return;
        var firm = "";
        // Try to find a firm column value
        Object.keys(row).forEach(function (k) {
          if (firm) return;
          var kl = k.toLowerCase();
          if (kl.indexOf("firm") !== -1 || kl.indexOf("fund") !== -1 || kl.indexOf("company") !== -1 || kl.indexOf("org") !== -1) {
            if (row[k] && row[k] !== name) firm = row[k];
          }
        });
        unmatched.push({ name: name.trim(), firm: firm.trim() });
      });

      if (unmatched.length >= 2) {
        unmatchedBody.innerHTML = unmatched.map(function (u) {
          return '<tr><td>' + escHtml(u.name) + '</td><td>' + escHtml(u.firm || '—') + '</td></tr>';
        }).join("");
        var countEl = document.getElementById("unmatched-count");
        if (countEl) countEl.textContent = String(unmatched.length);
        unmatchedSection.style.display = "block";
        unmatchedSection._candidates = unmatched;
      } else {
        unmatchedSection.style.display = "none";
      }
    }

    document.getElementById("upload-section").style.display = "none";
    document.getElementById("enrich-preview").style.display = "block";
  }

  function escHtml(s) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(s));
    return div.innerHTML;
  }

  // ── Download enriched CSV ──

  function downloadCSV() {
    if (!enrichedRows || !enrichedFields) return;
    var allRows = enrichedRows.concat(recommendedRows);
    var csv = Papa.unparse({ fields: enrichedFields, data: allRows });
    var blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "enriched_investors.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── File handling ──

  function processFile(file) {
    if (!index) {
      alert("Enrichment index not loaded yet. Please try again.");
      return;
    }
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: function (results) {
        if (!results.data || !results.data.length) {
          alert("CSV appears to be empty.");
          return;
        }
        var data = enrichRows(results.data, results.meta.fields);
        enrichedRows = data.rows;
        enrichedFields = data.fields;
        renderPreview(data);
      },
      error: function () {
        alert("Error parsing CSV file.");
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
      .then(function (data) {
        index = data;
        buildLookups();
      })
      .catch(function () { console.error("Failed to load enrichment index"); });

    var uploadArea = document.getElementById("upload-area");
    var fileInput = document.getElementById("file-input");

    uploadArea.addEventListener("click", function () { fileInput.click(); });

    fileInput.addEventListener("change", function () {
      if (this.files && this.files[0]) processFile(this.files[0]);
    });

    uploadArea.addEventListener("dragover", function (e) {
      e.preventDefault();
      this.classList.add("drag-over");
    });
    uploadArea.addEventListener("dragleave", function () {
      this.classList.remove("drag-over");
    });
    uploadArea.addEventListener("drop", function (e) {
      e.preventDefault();
      this.classList.remove("drag-over");
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        processFile(e.dataTransfer.files[0]);
      }
    });

    document.getElementById("download-btn").addEventListener("click", downloadCSV);

    var recToggleBtn = document.getElementById("rec-toggle");
    if (recToggleBtn) {
      recToggleBtn.addEventListener("click", function () {
        var sec = document.getElementById("rec-section");
        if (!sec) return;
        var showing = sec.style.display !== "none";
        sec.style.display = showing ? "none" : "block";
        if (showing) {
          this.innerHTML = "Show " + savedRecCount + " similar investors";
        } else {
          this.innerHTML = "Hide recommendations";
        }
      });
    }

    document.getElementById("reset-btn").addEventListener("click", function () {
      document.getElementById("upload-section").style.display = "block";
      document.getElementById("enrich-preview").style.display = "none";
      document.getElementById("rec-section").style.display = "none";
      document.getElementById("rec-toggle").style.display = "none";
      enrichedRows = null;
      enrichedFields = null;
      recommendedRows = [];
      fileInput.value = "";
      var unmatchedSection = document.getElementById("unmatched-section");
      if (unmatchedSection) {
        unmatchedSection.style.display = "none";
        unmatchedSection._candidates = null;
      }
    });

    // Unmatched candidates submit handler
    var submitCandidatesBtn = document.getElementById("submit-candidates-btn");
    if (submitCandidatesBtn) {
      submitCandidatesBtn.addEventListener("click", function () {
        var section = document.getElementById("unmatched-section");
        if (!section || !section._candidates || !section._candidates.length) return;
        if (typeof window.SeedlistFeedback !== "undefined" && window.SeedlistFeedback.submitCandidates) {
          window.SeedlistFeedback.submitCandidates(section._candidates);
        } else {
          alert("Feedback module not loaded.");
        }
      });
    }
  });
})();
