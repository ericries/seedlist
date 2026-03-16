/**
 * End-to-end test for the Seedlist CSV enrichment feature.
 *
 * Runs in Node.js with jsdom — no real browser required.
 * Execute:  node tests/test_enrich_e2e.js
 */

"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

// ── Sample enrichment index ──

const MOCK_INDEX = {
  investors: [
    {
      name: "Ron Conway",
      slug: "ron-conway",
      firm: "sv-angel",
      firm_name: "SV Angel",
      role: "Founder",
      location: "San Francisco, CA",
      stage_focus: ["seed"],
      sector_focus: ["fintech", "consumer-internet"],
      check_size: "$25K-$100K",
      last_active: "2023-06-15",
      status: "published",
      thesis_summary: "Based on 45 verified investments: 80% seed stage..."
    },
    {
      name: "Mike Maples",
      slug: "mike-maples",
      firm: "floodgate",
      firm_name: "Floodgate",
      role: "Partner",
      location: "Palo Alto, CA",
      stage_focus: ["seed"],
      sector_focus: ["enterprise"],
      check_size: "$500K-$2M",
      last_active: "2024-01-10",
      status: "published",
      thesis_summary: "Focuses on thunder lizards..."
    }
  ],
  firms: [
    {
      name: "Sequoia Capital",
      slug: "sequoia-capital",
      location: "Menlo Park, CA",
      stage_focus: ["seed", "series-a", "growth"],
      sector_focus: ["enterprise", "consumer"],
      fund_size: "$10B+",
      status: "published"
    }
  ],
  queued: [
    { name: "Chris Dixon", type: "individual", firm: "a16z" }
  ]
};

// Extended index for recommendation tests — adds investors that should be recommended
const MOCK_INDEX_WITH_RECS = JSON.parse(JSON.stringify(MOCK_INDEX));
MOCK_INDEX_WITH_RECS.investors.push(
  {
    name: "Alice Seedster",
    slug: "alice-seedster",
    firm: "acme-vc",
    firm_name: "Acme VC",
    role: "Partner",
    location: "San Francisco, CA",
    stage_focus: ["seed"],
    sector_focus: ["fintech", "consumer-internet"],
    check_size: "$100K-$500K",
    last_active: "2025-06-01",
    status: "published",
    thesis_summary: "Seed stage fintech and consumer."
  },
  {
    name: "Bob Enterprise",
    slug: "bob-enterprise",
    firm: "growth-co",
    firm_name: "Growth Co",
    role: "Partner",
    location: "New York, NY",
    stage_focus: ["seed", "series-a"],
    sector_focus: ["fintech", "enterprise"],
    check_size: "$1M-$5M",
    last_active: "2025-08-01",
    status: "published",
    thesis_summary: "Enterprise fintech at seed and series A."
  },
  {
    name: "Carol Biotech",
    slug: "carol-biotech",
    firm: "bio-fund",
    firm_name: "Bio Fund",
    role: "Partner",
    location: "Boston, MA",
    stage_focus: ["growth", "late-stage"],
    sector_focus: ["biotech", "pharma"],
    check_size: "$10M+",
    last_active: "2025-03-01",
    status: "published",
    thesis_summary: "Late stage biotech and pharma."
  }
);

// ── Minimal HTML that mirrors the template's DOM IDs ──

const HTML_SHELL = `<!DOCTYPE html>
<html>
<head><title>Enrich Test</title></head>
<body>
  <div id="upload-section" style="display:block">
    <div class="upload-area" id="upload-area">
      <input type="file" id="file-input" accept=".csv">
    </div>
  </div>
  <div id="enrich-preview" style="display:none">
    <div id="enrich-stats"></div>
    <button id="download-btn">Download</button>
    <button id="rec-toggle" style="display:none">Show <span id="rec-count">0</span> similar investors</button>
    <button id="reset-btn">Reset</button>
    <table>
      <thead id="enrich-thead"></thead>
      <tbody id="enrich-tbody"></tbody>
    </table>
    <div id="rec-section" style="display:none">
      <table>
        <thead id="rec-thead"></thead>
        <tbody id="rec-tbody"></tbody>
      </table>
    </div>
  </div>
</body>
</html>`;

// ── Helpers ──

/**
 * Create a jsdom window, wire up PapaParse + fetch mock, load enrich.js,
 * and return the window after DOMContentLoaded fires and the index is loaded.
 */
async function createEnv(customIndex) {
  const indexToUse = customIndex || MOCK_INDEX;
  const dom = new JSDOM(HTML_SHELL, {
    url: "https://seedlist.com/enrich.html",
    runScripts: "dangerously",
    resources: "usable",
    pretendToBeVisual: true
  });
  const { window } = dom;

  // Inject PapaParse into the global scope
  const papaCode = fs.readFileSync(
    path.join(__dirname, "..", "node_modules", "papaparse", "papaparse.min.js"),
    "utf8"
  );
  window.eval(papaCode);

  // Mock fetch to return the enrichment index
  window.fetch = function (_url) {
    return Promise.resolve({
      json: function () {
        return Promise.resolve(JSON.parse(JSON.stringify(indexToUse)));
      }
    });
  };

  // Mock URL.createObjectURL / revokeObjectURL (used by download)
  window.URL.createObjectURL = function () { return "blob:mock"; };
  window.URL.revokeObjectURL = function () {};

  // Mock alert
  window.alert = function (msg) { window._lastAlert = msg; };

  // Load enrich.js
  const enrichCode = fs.readFileSync(
    path.join(__dirname, "..", "static", "enrich.js"),
    "utf8"
  );
  window.eval(enrichCode);

  // Fire DOMContentLoaded so the IIFE's init block runs
  const evt = window.document.createEvent("Event");
  evt.initEvent("DOMContentLoaded", true, true);
  window.document.dispatchEvent(evt);

  // Wait for the fetch promise to resolve and buildLookups to complete
  await new Promise(function (resolve) { setTimeout(resolve, 50); });

  return { dom, window };
}

/**
 * Feed a CSV string through the enrichment pipeline by simulating
 * PapaParse.parse being called with the data directly.
 *
 * Returns the enrichment result data that renderPreview received.
 */
function processCSVString(window, csvString) {
  return new Promise(function (resolve) {
    // We can't easily trigger the file input, so we call Papa.parse
    // on the string the same way processFile would after reading a File.
    // But the IIFE captures everything. Instead, we'll intercept renderPreview
    // by watching the DOM for changes, then read the state from the DOM.

    // We'll use a different approach: directly invoke Papa.parse with the
    // CSV string, then call the enrichRows logic by running the same code
    // path through a synthetic approach.

    // Actually, the cleanest way: create a Blob from the CSV, make a File,
    // and programmatically set it on the file input, then trigger 'change'.

    // jsdom supports Blob and File:
    const file = new window.File([csvString], "test.csv", { type: "text/csv" });

    // Set the file on the input
    const fileInput = window.document.getElementById("file-input");

    // jsdom doesn't allow setting .files directly; we use defineProperty
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: true,
      configurable: true
    });

    // Trigger the change event
    const changeEvt = new window.Event("change", { bubbles: true });
    fileInput.dispatchEvent(changeEvt);

    // PapaParse runs synchronously for strings but async for File objects.
    // Give it a moment to complete.
    setTimeout(function () {
      resolve();
    }, 200);
  });
}

/**
 * Parse the stats from the DOM after enrichment.
 */
function readStats(window) {
  const doc = window.document;
  const statsEl = doc.getElementById("enrich-stats");
  const items = statsEl.querySelectorAll(".stat-item");
  const stats = {};
  items.forEach(function (item) {
    const label = item.querySelector(".stat-label");
    const number = item.querySelector(".stat-number");
    if (label && number) {
      stats[label.textContent.trim().toLowerCase()] = number.textContent.trim();
    }
  });
  return stats;
}

/**
 * Read the preview table rows from the DOM.
 */
function readPreviewRows(window) {
  const doc = window.document;
  const thead = doc.getElementById("enrich-thead");
  const tbody = doc.getElementById("enrich-tbody");
  const headers = [];
  const headerCells = thead.querySelectorAll("th");
  headerCells.forEach(function (th) { headers.push(th.textContent.trim()); });

  const rows = [];
  const trs = tbody.querySelectorAll("tr");
  trs.forEach(function (tr) {
    const cells = tr.querySelectorAll("td");
    if (cells.length === headers.length) {
      const row = {};
      cells.forEach(function (td, i) {
        // For URL columns, check for an anchor
        const a = td.querySelector("a");
        row[headers[i]] = a ? a.getAttribute("href") : td.textContent.trim();
      });
      rows.push(row);
    }
  });
  return { headers, rows };
}

// ── Tests ──

let passed = 0;
let failed = 0;

async function test(name, fn) {
  try {
    await fn();
    passed++;
    console.log("  PASS: " + name);
  } catch (err) {
    failed++;
    console.log("  FAIL: " + name);
    console.log("        " + err.message);
    if (err.stack) {
      // Show first relevant stack line
      const lines = err.stack.split("\n");
      for (let i = 1; i < Math.min(4, lines.length); i++) {
        if (lines[i].includes("test_enrich")) {
          console.log("        " + lines[i].trim());
        }
      }
    }
  }
}

async function runTests() {
  console.log("\nSeedlist Enrich E2E Tests\n");

  // ── 1. Exact match ──
  await test("Exact match: 'Ron Conway' matches investor profile", async function () {
    const { window } = await createEnv();
    const csv = "Name,Email\nRon Conway,ron@sv.angel\nMike Maples,mike@floodgate.com\n";
    await processCSVString(window, csv);

    const { rows } = readPreviewRows(window);
    assert.ok(rows.length >= 2, "Expected at least 2 rows, got " + rows.length);

    const ron = rows[0];
    assert.strictEqual(ron.seedlist_match, "exact", "Ron Conway should be exact match");
    assert.strictEqual(ron.seedlist_confidence, "1", "Exact match confidence should be 1");
    assert.ok(
      ron.seedlist_url.includes("ron-conway"),
      "URL should contain ron-conway slug"
    );

    const mike = rows[1];
    assert.strictEqual(mike.seedlist_match, "exact", "Mike Maples should be exact match");
    window.close();
  });

  // ── 2. Fuzzy match ──
  await test("Fuzzy match: 'Ron Conwey' (misspelled) still matches", async function () {
    const { window } = await createEnv();
    const csv = "Name\nRon Conwey\n";
    await processCSVString(window, csv);

    const { rows } = readPreviewRows(window);
    assert.ok(rows.length >= 1, "Expected at least 1 row");
    assert.strictEqual(rows[0].seedlist_match, "fuzzy", "Misspelled name should fuzzy match");
    const conf = parseFloat(rows[0].seedlist_confidence);
    assert.ok(conf >= 0.75 && conf < 1.0, "Fuzzy confidence should be >= 0.75 and < 1.0, got " + conf);
    assert.ok(
      rows[0].seedlist_url.includes("ron-conway"),
      "Fuzzy match should resolve to ron-conway profile"
    );
    window.close();
  });

  // ── 3. Firm-only match ──
  await test("Firm-only match: 'Sequoia Capital' matches firm profile", async function () {
    const { window } = await createEnv();
    const csv = "Name\nSequoia Capital\n";
    await processCSVString(window, csv);

    const { rows } = readPreviewRows(window);
    assert.ok(rows.length >= 1, "Expected at least 1 row");
    assert.strictEqual(rows[0].seedlist_match, "firm_only", "Sequoia Capital should be firm_only match");
    assert.ok(
      rows[0].seedlist_url.includes("sequoia-capital"),
      "URL should contain sequoia-capital slug"
    );
    window.close();
  });

  // ── 4. No match ──
  await test("No match: 'Unknown Person' returns none", async function () {
    const { window } = await createEnv();
    const csv = "Name\nUnknown Person\n";
    await processCSVString(window, csv);

    const { rows } = readPreviewRows(window);
    assert.ok(rows.length >= 1, "Expected at least 1 row");
    assert.strictEqual(rows[0].seedlist_match, "none", "Unknown Person should be 'none'");
    assert.strictEqual(rows[0].seedlist_confidence, "0", "No match confidence should be 0");
    window.close();
  });

  // ── 5. Column auto-detection ──
  await test("Column auto-detection: picks 'Investor' as name column from headers", async function () {
    const { window } = await createEnv();
    // The "Investor" column has names that match the index, so it should be auto-detected
    const csv = "Email,Investor,Firm,Notes\njohn@x.com,Ron Conway,SV Angel,test\njane@x.com,Mike Maples,Floodgate,test\n";
    await processCSVString(window, csv);

    const { headers, rows } = readPreviewRows(window);
    // The first column in the preview should be the detected name column
    assert.strictEqual(headers[0], "Investor", "Auto-detected name column should be 'Investor'");
    assert.strictEqual(rows[0].seedlist_match, "exact", "Should match Ron Conway exactly");
    window.close();
  });

  // ── 6. Stats calculation ──
  await test("Stats are calculated correctly", async function () {
    const { window } = await createEnv();
    // 2 exact, 1 fuzzy, 1 firm_only, 1 none = 5 total, 4 matched = 80%
    const csv = "Name\nRon Conway\nMike Maples\nRon Conwey\nSequoia Capital\nUnknown Person\n";
    await processCSVString(window, csv);

    const stats = readStats(window);
    assert.strictEqual(stats.exact, "2", "Should have 2 exact matches");
    assert.strictEqual(stats.fuzzy, "1", "Should have 1 fuzzy match");
    assert.strictEqual(stats["firm only"], "1", "Should have 1 firm-only match");
    assert.strictEqual(stats["no match"], "1", "Should have 1 no match");
    assert.strictEqual(stats["match rate"], "80%", "Match rate should be 80%");
    window.close();
  });

  // ── 7. UI state: upload hidden, preview shown after processing ──
  await test("UI state toggles: upload hidden, preview shown after CSV", async function () {
    const { window } = await createEnv();
    const doc = window.document;

    // Before processing
    assert.strictEqual(
      doc.getElementById("upload-section").style.display, "block",
      "Upload section should be visible initially"
    );
    assert.strictEqual(
      doc.getElementById("enrich-preview").style.display, "none",
      "Preview should be hidden initially"
    );

    const csv = "Name\nRon Conway\n";
    await processCSVString(window, csv);

    assert.strictEqual(
      doc.getElementById("upload-section").style.display, "none",
      "Upload section should be hidden after processing"
    );
    assert.strictEqual(
      doc.getElementById("enrich-preview").style.display, "block",
      "Preview should be visible after processing"
    );
    window.close();
  });

  // ── 8. Reset button restores initial state ──
  await test("Reset button restores upload view", async function () {
    const { window } = await createEnv();
    const doc = window.document;
    const csv = "Name\nRon Conway\n";
    await processCSVString(window, csv);

    // Click reset
    doc.getElementById("reset-btn").click();

    assert.strictEqual(
      doc.getElementById("upload-section").style.display, "block",
      "Upload section should reappear after reset"
    );
    assert.strictEqual(
      doc.getElementById("enrich-preview").style.display, "none",
      "Preview should be hidden after reset"
    );
    window.close();
  });

  // ── 9. Queued investor match ──
  await test("Queued match: 'Chris Dixon' shows as queued", async function () {
    const { window } = await createEnv();
    const csv = "Name\nChris Dixon\n";
    await processCSVString(window, csv);

    const { rows } = readPreviewRows(window);
    assert.ok(rows.length >= 1, "Expected at least 1 row");
    assert.strictEqual(rows[0].seedlist_match, "queued", "Chris Dixon should match as queued");
    window.close();
  });

  // ── 10. Enrichment columns are added ──
  await test("Enriched output includes all seedlist columns", async function () {
    const { window } = await createEnv();
    const csv = "Name,Email\nRon Conway,ron@test.com\n";
    await processCSVString(window, csv);

    // Check the preview table has enrichment columns
    const { headers } = readPreviewRows(window);
    assert.ok(headers.includes("seedlist_match"), "Should have seedlist_match column");
    assert.ok(headers.includes("seedlist_confidence"), "Should have seedlist_confidence column");
    assert.ok(headers.includes("seedlist_url"), "Should have seedlist_url column");
    window.close();
  });

  // ── 11. Firm column fallback: name column misses, firm column catches ──
  await test("Firm column fallback: no name match but firm column matches", async function () {
    const { window } = await createEnv();
    // "John Nobody" won't match anything, but "Sequoia Capital" in the Firm column should
    const csv = "Investor,Firm\nJohn Nobody,Sequoia Capital\n";
    await processCSVString(window, csv);

    const { rows } = readPreviewRows(window);
    assert.ok(rows.length >= 1, "Expected at least 1 row");
    assert.strictEqual(rows[0].seedlist_match, "firm_only", "Should fall back to firm column match");
    window.close();
  });

  // ── 12. Download button produces CSV via Papa.unparse ──
  await test("Download triggers Papa.unparse with correct data", async function () {
    const { window } = await createEnv();
    const csv = "Name\nRon Conway\nUnknown Person\n";
    await processCSVString(window, csv);

    // Intercept Papa.unparse to capture what it receives
    let unparsedData = null;
    const origUnparse = window.Papa.unparse;
    window.Papa.unparse = function (input) {
      unparsedData = input;
      return origUnparse.call(window.Papa, input);
    };

    // Mock the click on download anchor
    let downloadTriggered = false;
    const origCreateElement = window.document.createElement.bind(window.document);
    window.document.createElement = function (tag) {
      const el = origCreateElement(tag);
      if (tag === "a") {
        el.click = function () { downloadTriggered = true; };
      }
      return el;
    };

    window.document.getElementById("download-btn").click();

    assert.ok(unparsedData, "Papa.unparse should have been called");
    assert.ok(Array.isArray(unparsedData.fields), "Should have fields array");
    assert.ok(Array.isArray(unparsedData.data), "Should have data array");
    assert.strictEqual(unparsedData.data.length, 2, "Should have 2 data rows");

    // Verify enrichment fields are present
    const expectedFields = [
      "seedlist_match", "seedlist_confidence", "seedlist_url", "seedlist_status",
      "investor_stage_focus", "investor_sector_focus", "investor_check_size",
      "investor_location", "firm_name", "last_active", "inferred_thesis_summary"
    ];
    expectedFields.forEach(function (f) {
      assert.ok(unparsedData.fields.includes(f), "Fields should include " + f);
    });

    // Verify the enriched data
    const ronRow = unparsedData.data[0];
    assert.strictEqual(ronRow.Name, "Ron Conway", "Original Name column preserved");
    assert.strictEqual(ronRow.seedlist_match, "exact");
    assert.strictEqual(ronRow.investor_check_size, "$25K-$100K");
    assert.strictEqual(ronRow.firm_name, "SV Angel");
    assert.strictEqual(ronRow.investor_location, "San Francisco, CA");
    assert.strictEqual(ronRow.investor_stage_focus, "seed");
    assert.strictEqual(ronRow.investor_sector_focus, "fintech, consumer-internet");

    assert.ok(downloadTriggered, "Download link click should have been triggered");
    window.close();
  });

  // ── 13. Recommendations: similar investors are shown ──
  await test("Recommendations: similar seed/fintech investors recommended, biotech excluded", async function () {
    const { window } = await createEnv(MOCK_INDEX_WITH_RECS);
    // Upload CSV with Ron Conway and Mike Maples (both seed/fintech)
    const csv = "Name\nRon Conway\nMike Maples\n";
    await processCSVString(window, csv);

    const doc = window.document;
    const recToggle = doc.getElementById("rec-toggle");
    const recSection = doc.getElementById("rec-section");

    // Rec toggle should be visible (we have candidates)
    assert.notStrictEqual(recToggle.style.display, "none", "Rec toggle should be visible");

    // Rec section should be hidden until toggled
    assert.strictEqual(recSection.style.display, "none", "Rec section hidden by default");

    // Read recommendation rows
    const recBody = doc.getElementById("rec-tbody");
    const recRows = recBody.querySelectorAll("tr");
    const recNames = [];
    recRows.forEach(function (tr) {
      const cells = tr.querySelectorAll("td");
      if (cells.length > 0) recNames.push(cells[0].textContent.trim());
    });

    // Alice (seed/fintech) and Bob (seed+series-a/fintech+enterprise) should be recommended
    // Carol (growth/biotech) should NOT be recommended
    assert.ok(recNames.includes("Alice Seedster"), "Alice Seedster should be recommended (seed/fintech overlap)");
    assert.ok(!recNames.includes("Carol Biotech"), "Carol Biotech should NOT be recommended (biotech/growth mismatch)");

    // Rec rows should have match type "recommended"
    const firstRecRow = recBody.querySelector("tr");
    const matchCell = firstRecRow.querySelectorAll("td")[1]; // seedlist_match column
    assert.strictEqual(matchCell.textContent.trim(), "recommended");
    window.close();
  });

  // ── 14. Recommendations toggle show/hide ──
  await test("Recommendations: toggle button shows and hides section", async function () {
    const { window } = await createEnv(MOCK_INDEX_WITH_RECS);
    const csv = "Name\nRon Conway\nMike Maples\n";
    await processCSVString(window, csv);

    const doc = window.document;
    const recToggle = doc.getElementById("rec-toggle");
    const recSection = doc.getElementById("rec-section");

    // Click toggle to show
    recToggle.click();
    assert.strictEqual(recSection.style.display, "block", "Rec section should be visible after toggle");
    assert.ok(recToggle.textContent.includes("Hide"), "Button should say Hide after showing");

    // Click toggle to hide
    recToggle.click();
    assert.strictEqual(recSection.style.display, "none", "Rec section should be hidden after second toggle");
    window.close();
  });

  // ── 15. Recommendations included in CSV download ──
  await test("Recommendations: included in downloaded CSV", async function () {
    const { window } = await createEnv(MOCK_INDEX_WITH_RECS);
    const csv = "Name\nRon Conway\nMike Maples\n";
    await processCSVString(window, csv);

    // Intercept Papa.unparse
    let unparsedData = null;
    const origUnparse = window.Papa.unparse;
    window.Papa.unparse = function (input) {
      unparsedData = input;
      return origUnparse.call(window.Papa, input);
    };

    const origCreateElement = window.document.createElement.bind(window.document);
    window.document.createElement = function (tag) {
      const el = origCreateElement(tag);
      if (tag === "a") { el.click = function () {}; }
      return el;
    };

    window.document.getElementById("download-btn").click();

    assert.ok(unparsedData, "Papa.unparse should have been called");
    // Should have original rows + recommendation rows
    assert.ok(unparsedData.data.length > 2, "Download should include more than 2 rows (originals + recommendations)");

    const recRows = unparsedData.data.filter(function (r) { return r.seedlist_match === "recommended"; });
    assert.ok(recRows.length > 0, "Download should include recommended rows");

    // Verify rec rows have proper enrichment data
    const aliceRow = recRows.find(function (r) { return r.Name === "Alice Seedster"; });
    if (aliceRow) {
      assert.ok(aliceRow.seedlist_url.includes("alice-seedster"), "Rec row should have correct URL");
      assert.ok(aliceRow.investor_stage_focus.includes("seed"), "Rec row should have stage focus");
    }
    window.close();
  });

  // ── 16. No recommendations with insufficient matches ──
  await test("Recommendations: not shown with only 1 matched investor", async function () {
    const { window } = await createEnv(MOCK_INDEX_WITH_RECS);
    // Only 1 match — not enough to build a target profile
    const csv = "Name\nRon Conway\nUnknown Person\nAnother Nobody\n";
    await processCSVString(window, csv);

    const doc = window.document;
    const recToggle = doc.getElementById("rec-toggle");
    assert.strictEqual(recToggle.style.display, "none", "Rec toggle should be hidden with < 2 matches");
    window.close();
  });

  // ── Summary ──
  console.log("\n" + passed + " passed, " + failed + " failed, " + (passed + failed) + " total\n");
  if (failed > 0) process.exit(1);
}

runTests().catch(function (err) {
  console.error("Test runner error:", err);
  process.exit(1);
});
