/* Seedlist Feedback — source submission & CSV candidate reporting */

(function () {
  "use strict";

  var GITHUB_REPO = "ericries/seedlist";
  var MAX_URL_LENGTH = 2048;

  // ── Shared utilities ──

  function buildGitHubIssueUrl(title, body, label) {
    var base = "https://github.com/" + GITHUB_REPO + "/issues/new";
    var params = "?title=" + encodeURIComponent(title) +
      "&body=" + encodeURIComponent(body) +
      "&labels=" + encodeURIComponent(label);
    return base + params;
  }

  // ── URL validation ──

  function validateUrl(url) {
    if (!url || !url.trim()) {
      return "Please enter a URL.";
    }
    url = url.trim();
    if (url.length > MAX_URL_LENGTH) {
      return "URL is too long (max " + MAX_URL_LENGTH + " characters).";
    }
    var parsed;
    try {
      parsed = new URL(url);
    } catch (e) {
      return "That doesn't look like a valid URL.";
    }
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return "Only http and https URLs are accepted.";
    }
    return null;
  }

  // ── Feature 1: Source URL submission ──

  var activeForm = null;

  function showUrlForm(slug, profileType) {
    hideUrlForm();

    var anchor = document.querySelector(".profile-header");
    if (!anchor) return;

    var form = document.createElement("div");
    form.id = "seedlist-url-form";
    form.className = "feedback-form";

    form.innerHTML =
      '<div class="feedback-hint" style="margin-bottom:0.5rem;font-weight:600;color:var(--color-text);">Submit a source URL for this profile</div>' +
      '<div class="feedback-input-row">' +
        '<input type="url" id="seedlist-url-input" placeholder="https://example.com/article" />' +
        '<button id="seedlist-url-submit" class="btn-submit">Submit</button>' +
        '<button id="seedlist-url-cancel" class="btn-cancel">Cancel</button>' +
      '</div>' +
      '<div id="seedlist-url-error" class="feedback-error" style="display:none;"></div>';

    anchor.parentNode.insertBefore(form, anchor.nextSibling);
    activeForm = form;

    var input = document.getElementById("seedlist-url-input");
    input.focus();

    document.getElementById("seedlist-url-submit").addEventListener("click", function () {
      submitSourceUrl(slug, profileType, input.value);
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        submitSourceUrl(slug, profileType, input.value);
      }
    });

    document.getElementById("seedlist-url-cancel").addEventListener("click", function (e) {
      e.preventDefault();
      hideUrlForm();
    });
  }

  function hideUrlForm() {
    if (activeForm) {
      activeForm.parentNode.removeChild(activeForm);
      activeForm = null;
    }
  }

  function submitSourceUrl(slug, profileType, url) {
    var errorEl = document.getElementById("seedlist-url-error");
    if (errorEl) errorEl.style.display = "none";

    var error = validateUrl(url);
    if (error) {
      if (errorEl) {
        errorEl.textContent = error;
        errorEl.style.display = "block";
      }
      return;
    }

    url = url.trim();
    var title = "Source: " + slug;
    var body =
      "<!-- source-submission -->\n" +
      "slug: " + slug + "\n" +
      "type: " + profileType + "\n" +
      "url: " + url;

    var issueUrl = buildGitHubIssueUrl(title, body, "source-submission");
    window.open(issueUrl, "_blank");
    hideUrlForm();
  }

  // ── Feature 2: CSV candidate submission ──

  function submitCandidates(candidates) {
    if (!candidates || !candidates.length) return;

    // GitHub GET URLs have a practical limit (~8192 chars).
    // Batch candidates into chunks that fit within the limit.
    var URL_LIMIT = 7500; // conservative limit for encoded URL
    var batches = [];
    var current = [];

    candidates.forEach(function (c) {
      current.push(c);
      // Test if current batch would exceed URL limit
      var testBody = buildCandidateBody(current, candidates.length, batches.length + 1);
      var testTitle = "CSV candidates: " + candidates.length + " investors (part " + (batches.length + 1) + ")";
      var testUrl = buildGitHubIssueUrl(testTitle, testBody, "csv-unmatched");
      if (testUrl.length > URL_LIMIT && current.length > 1) {
        // Remove last item, finalize this batch
        current.pop();
        batches.push(current);
        current = [c];
      }
    });
    if (current.length) batches.push(current);

    batches.forEach(function (batch, i) {
      var part = batches.length > 1 ? " (part " + (i + 1) + "/" + batches.length + ")" : "";
      var title = "CSV candidates: " + candidates.length + " investors" + part;
      var body = buildCandidateBody(batch, candidates.length, i + 1);
      var issueUrl = buildGitHubIssueUrl(title, body, "csv-unmatched");
      window.open(issueUrl, "_blank");
    });
  }

  function buildCandidateBody(batch, totalCount, partNum) {
    var lines = ["<!-- csv-unmatched -->"];
    lines.push("submitted: " + new Date().toISOString());
    lines.push("total_candidates: " + totalCount);
    lines.push("candidates:");
    batch.forEach(function (c) {
      lines.push('  - name: "' + (c.name || "").replace(/"/g, '\\"') + '"');
      lines.push('    firm: "' + (c.firm || "").replace(/"/g, '\\"') + '"');
    });
    return lines.join("\n");
  }

  // ── Public API ──

  window.SeedlistFeedback = {
    showUrlForm: showUrlForm,
    hideUrlForm: hideUrlForm,
    submitSourceUrl: submitSourceUrl,
    submitCandidates: submitCandidates,
    buildGitHubIssueUrl: buildGitHubIssueUrl
  };
})();
