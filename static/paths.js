/* Seedlist — Paths to Investor feature */

(function () {
  "use strict";

  var MAX_CO_INVESTORS = 10;
  var MAX_PORTFOLIO_COMPANIES = 5;
  var MAX_BACKERS_PER_COMPANY = 8;

  function escHtml(s) {
    if (!s) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function init() {
    var section = document.getElementById("paths-section");
    if (!section) return;

    var slug = section.getAttribute("data-slug");
    if (!slug) return;

    fetch("/investor-graph.json")
      .then(function (res) { return res.json(); })
      .then(function (graph) { render(graph, slug, section); })
      .catch(function () { /* silently fail — section stays hidden */ });
  }

  function investorLink(slug, name, graph) {
    var displayName = escHtml(name || graph.investor_names[slug] || slug);
    if (graph.investor_names[slug]) {
      return '<a href="/investors/' + escHtml(slug) + '.html" class="paths-name">' + displayName + '</a>';
    }
    return '<span class="paths-name">' + displayName + '</span>';
  }

  function render(graph, slug, section) {
    var html = "";

    // A. Co-investors
    var coData = graph.co_investments[slug];
    if (coData) {
      var pairs = [];
      for (var peer in coData) {
        if (coData.hasOwnProperty(peer)) {
          pairs.push({ slug: peer, count: coData[peer].count, companies: coData[peer].companies });
        }
      }
      pairs.sort(function (a, b) { return b.count - a.count; });
      pairs = pairs.slice(0, MAX_CO_INVESTORS);

      if (pairs.length > 0) {
        html += '<div class="paths-category">';
        html += '<h3>Through co-investors</h3>';
        html += '<ul class="paths-list">';
        for (var i = 0; i < pairs.length; i++) {
          var p = pairs[i];
          var firmStr = graph.investor_firms[p.slug] ? " (" + escHtml(graph.investor_firms[p.slug]) + ")" : "";
          var companyNames = p.companies.map(function (c) { return escHtml(c); }).join(", ");
          html += '<li>';
          html += investorLink(p.slug, null, graph) + firmStr;
          html += ' <span class="paths-detail">&mdash; ' + p.count + ' shared investment' + (p.count !== 1 ? 's' : '') + '</span>';
          html += '<div class="paths-companies">' + companyNames + '</div>';
          html += '</li>';
        }
        html += '</ul></div>';
      }
    }

    // B. Firm colleagues
    var firmSlug = null;
    for (var fSlug in graph.firms) {
      if (graph.firms.hasOwnProperty(fSlug)) {
        var members = graph.firms[fSlug].members;
        if (members.indexOf(slug) !== -1) {
          firmSlug = fSlug;
          break;
        }
      }
    }
    if (firmSlug) {
      var firmInfo = graph.firms[firmSlug];
      var colleagues = firmInfo.members.filter(function (m) { return m !== slug; });
      if (colleagues.length > 0) {
        html += '<div class="paths-category">';
        html += '<h3>Through firm colleagues</h3>';
        html += '<p class="paths-detail">At ' + escHtml(firmInfo.name) + ':</p>';
        html += '<ul class="paths-list">';
        for (var c = 0; c < colleagues.length; c++) {
          html += '<li>' + investorLink(colleagues[c], null, graph) + '</li>';
        }
        html += '</ul></div>';
      }
    }

    // C. Through portfolio company founders
    // Find startups this investor backed that have founder data
    var companiesWithFounders = [];
    for (var startup in graph.startup_backers) {
      if (graph.startup_backers.hasOwnProperty(startup)) {
        var backers = graph.startup_backers[startup];
        if (backers.indexOf(slug) !== -1) {
          var founders = (graph.startup_founders && graph.startup_founders[startup]) || [];
          if (founders.length > 0) {
            companiesWithFounders.push({ slug: startup, founders: founders });
          }
        }
      }
    }
    companiesWithFounders.sort(function (a, b) { return b.founders.length - a.founders.length; });
    companiesWithFounders = companiesWithFounders.slice(0, MAX_PORTFOLIO_COMPANIES);

    if (companiesWithFounders.length > 0) {
      html += '<div class="paths-category">';
      html += '<h3>Through portfolio company founders</h3>';
      html += '<p class="paths-detail">Founders of companies this investor backed &mdash; they can make a warm intro.</p>';
      html += '<ul class="paths-list">';
      for (var k = 0; k < companiesWithFounders.length; k++) {
        var co = companiesWithFounders[k];
        var companyName = (graph.startup_names && graph.startup_names[co.slug]) || co.slug;
        var founderNames = co.founders.map(function (f) {
          var role = f.role ? ' <span class="paths-detail">(' + escHtml(f.role) + ')</span>' : '';
          return '<span class="paths-name">' + escHtml(f.name) + '</span>' + role;
        }).join(", ");
        html += '<li>';
        html += '<a href="/startups/' + escHtml(co.slug) + '.html" class="paths-name">' + escHtml(companyName) + '</a>';
        html += '<div class="paths-companies">' + founderNames + '</div>';
        html += '</li>';
      }
      html += '</ul></div>';
    }

    // D. Collections
    var cols = graph.collections[slug];
    if (cols && cols.length > 0) {
      html += '<div class="paths-category">';
      html += '<h3>Through groups</h3>';
      html += '<p class="paths-detail">Member of: ';
      html += cols.map(function (c) {
        return '<a href="/investors/groups.html">' + escHtml(c) + '</a>';
      }).join(", ");
      html += '</p></div>';
    }

    if (html) {
      document.getElementById("paths-content").innerHTML = html;
      section.style.display = "";
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
