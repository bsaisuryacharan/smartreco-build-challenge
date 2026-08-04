(function () {
  "use strict";

  var BATCH_SIZE = 5;
  var FLUSH_MS = 10000;

  var queue = [];
  var flushTimer = null;
  var pageEnterTime = Date.now();

  function attr(selector, key) {
    var el = document.querySelector(selector);
    return el ? el.getAttribute(key) : null;
  }

  function currentProductId() {
    return attr("[data-product-id]", "data-product-id");
  }

  function currentCategory() {
    return attr("[data-category]", "data-category") || "";
  }

  // ── Queue & flush ────────────────────────────────────────────────────

  function enqueue(type, meta) {
    queue.push({
      event_type: type,
      product_id: (meta && meta.product_id != null)
        ? meta.product_id
        : (currentProductId() ? parseInt(currentProductId(), 10) : null),
      metadata: meta || {},
      timestamp: new Date().toISOString(),
    });
    if (queue.length >= BATCH_SIZE) {
      flush();
    }
  }

  function flush() {
    if (!queue.length) return;
    var payload = JSON.stringify({ events: queue.splice(0) });
    try {
      // sendBeacon is fire-and-forget and survives page unload
      if (navigator.sendBeacon) {
        var blob = new Blob([payload], { type: "application/json" });
        navigator.sendBeacon("/api/events/batch", blob);
      } else {
        fetch("/api/events/batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
          keepalive: true,
        });
      }
    } catch (_) {
      // Never let tracking errors surface to users
    }
  }

  function startTimer() {
    if (flushTimer) clearInterval(flushTimer);
    flushTimer = setInterval(flush, FLUSH_MS);
  }

  // ── Page / product view ──────────────────────────────────────────────

  var pid = currentProductId();
  if (pid) {
    enqueue("product_view", {
      product_id: parseInt(pid, 10),
      category: currentCategory(),
    });
  } else {
    enqueue("page_view", { path: window.location.pathname });
  }

  // ── Click tracking ───────────────────────────────────────────────────

  document.addEventListener("click", function (e) {
    try {
      // Find the closest ancestor that's a product card in the grid
      var card = e.target.closest("[data-product-id]");
      // Exclude the product detail article (we already fired product_view)
      var detailArticle = document.querySelector("article[data-product-id]");
      if (card && card !== detailArticle) {
        enqueue("click", {
          product_id: parseInt(card.getAttribute("data-product-id"), 10),
          category: card.getAttribute("data-category") || "",
        });
      }
    } catch (_) {}
  });

  // ── Search tracking ──────────────────────────────────────────────────

  var searchForm = document.querySelector('form[action="/search"]');
  if (searchForm) {
    searchForm.addEventListener("submit", function () {
      try {
        var input = searchForm.querySelector('input[name="q"]');
        var q = input ? input.value.trim() : "";
        if (q) enqueue("search", { query: q });
        flush(); // flush immediately before navigation
      } catch (_) {}
    });
  }

  // ── Time-spent on page unload ────────────────────────────────────────

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") {
      try {
        var seconds = Math.round((Date.now() - pageEnterTime) / 1000);
        if (seconds >= 5) {
          enqueue("time_spent", {
            product_id: pid ? parseInt(pid, 10) : null,
            duration_seconds: seconds,
            path: window.location.pathname,
          });
        }
      } catch (_) {}
      flush();
    }
    if (document.visibilityState === "visible") {
      pageEnterTime = Date.now();
    }
  });

  window.addEventListener("beforeunload", flush);

  // ── Recommendation panel live polling ────────────────────────────────

  function updatePanel(data) {
    var narrativeEl = document.getElementById("rec-narrative");
    var productsEl = document.getElementById("rec-products");
    if (!narrativeEl) return;

    if (data.narrative) {
      narrativeEl.classList.remove("rec-loading");
      narrativeEl.textContent = data.narrative;
    } else if (narrativeEl.classList.contains("rec-loading")) {
      narrativeEl.textContent = "Browse some courses and we’ll personalize this for you!";
    }

    if (productsEl && data.products && data.products.length) {
      productsEl.innerHTML = data.products
        .map(function (p) {
          return (
            '<div class="rec-product-card" data-product-id="' +
            p.id +
            '" data-category="' +
            (p.category || "") +
            '">' +
            '<a href="/product/' +
            p.id +
            '">' +
            _esc(p.title) +
            "</a>" +
            '<div class="rec-product-meta">' +
            '<span class="badge">' + _esc(p.category) + "</span>" +
            '<span class="price">$' + p.price.toFixed(2) + "</span>" +
            "</div></div>"
          );
        })
        .join("");
    }
  }

  function _esc(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function pollRecommendations() {
    fetch("/api/recommendations")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data) updatePanel(data); })
      .catch(function () {});
  }

  pollRecommendations();
  setInterval(pollRecommendations, 30000);

  startTimer();
})();
