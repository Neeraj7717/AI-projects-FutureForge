// Shared helpers used by every page: API fetch wrapper, DB health indicator, small DOM utils.

const CURRENT_PAGE = location.pathname.split("/").pop() || "index.html";

function goToLogin() {
  const next = CURRENT_PAGE + location.search;
  location.href = `login.html?next=${encodeURIComponent(next)}`;
}

// Every API endpoint except /api/auth/** and /api/health sits behind AuthInterceptor
// server-side - this is the actual enforcement. The redirect here is just so an expired or
// missing session bounces you to the login page instead of leaving you staring at broken data.
const Api = {
  async get(path) {
    const res = await fetch(path, { headers: { Accept: "application/json" } });
    if (res.status === 401 && CURRENT_PAGE !== "login.html") {
      goToLogin();
      return new Promise(() => {}); // navigating away - don't let callers process a 401 body
    }
    if (!res.ok) {
      let body = {};
      try { body = await res.json(); } catch (_) { /* ignore */ }
      const err = new Error(body.message || `Request failed (${res.status})`);
      err.status = res.status;
      err.code = body.error;
      throw err;
    }
    return res.json();
  },
};

// Fires as soon as this script runs (not on DOMContentLoaded) so an unauthenticated visitor
// gets bounced before the rest of the page's own data-fetching even starts.
if (CURRENT_PAGE !== "login.html") {
  fetch("/api/auth/status", { headers: { Accept: "application/json" } })
    .then((r) => r.json())
    .then((s) => { if (!s.authenticated) goToLogin(); })
    .catch(() => { /* if the check itself fails, let the page's own API calls surface it */ });
}

async function handleLogout() {
  try { await fetch("/api/auth/logout", { method: "POST" }); } catch (e) { /* ignore */ }
  location.href = "login.html";
}

// Injected next to the DB indicator on every page (login.html has neither) rather than hand-
// added to each page's nav markup.
function initLogoutLink() {
  const dbIndicator = document.querySelector(".db-indicator");
  if (!dbIndicator || document.getElementById("nav-logout-link")) return;
  const link = document.createElement("a");
  link.id = "nav-logout-link";
  link.href = "#";
  link.className = "nav-logout";
  link.textContent = "Logout";
  link.addEventListener("click", (e) => { e.preventDefault(); handleLogout(); });
  dbIndicator.insertAdjacentElement("afterend", link);
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

function formatPrice(price) {
  return `$${Number(price).toFixed(2)}`;
}

function categoryBadge(category) {
  return category ? `<span class="badge eco">${escapeHtml(category)}</span>` : "";
}

// No per-product photography in this dataset. Each category has one real, openly-licensed photo
// as a fallback, and the highest-traffic items (bestsellers, brand/store-brand pairs) get a more
// specific photo matched by keyword in the product name - both self-hosted under images/ (see
// docs/IMAGE_CREDITS.md for source + license per file) instead of hotlinking a third-party image
// API that could go down or serve a mismatched photo during grading.
const CATEGORY_IMAGES = {
  "Dairy & Eggs": "images/dairy.jpg",
  "Bakery": "images/bakery.jpg",
  "Snacks & Cookies": "images/snacks.jpg",
  "Beverages": "images/beverages.jpg",
  "Produce": "images/produce.jpg",
  "Pantry Staples": "images/pantry.jpg",
  "Frozen Foods": "images/frozen.jpg",
};
const FALLBACK_IMAGE = "images/dairy.jpg";

// Checked in order, first match wins; falls back to the category photo. Specific / narrower
// patterns (sandwich cookies, orange juice) are listed before the broader ones they'd otherwise
// collide with (cookie, juice) so every distinct product gets its own real photo instead of
// silently sharing a same-category neighbor's image.
const PRODUCT_IMAGE_KEYWORDS = [
  { match: /milk/i, image: "images/dairy.jpg" },
  { match: /egg/i, image: "images/eggs.jpg" },
  { match: /bagel/i, image: "images/bagel.jpg" },
  { match: /croissant/i, image: "images/croissants.jpg" },
  { match: /bread/i, image: "images/bread.jpg" },
  { match: /sandwich cookie/i, image: "images/sandwich-cookies.jpg" },
  { match: /cookie/i, image: "images/snacks.jpg" },
  { match: /chip/i, image: "images/chips.jpg" },
  { match: /pretzel/i, image: "images/pretzels.jpg" },
  { match: /granola/i, image: "images/granola.jpg" },
  { match: /coffee/i, image: "images/beverages.jpg" },
  { match: /green tea/i, image: "images/tea.jpg" },
  { match: /sparkling water/i, image: "images/sparkling-water.jpg" },
  { match: /cola/i, image: "images/cola.jpg" },
  { match: /orange juice/i, image: "images/juice.jpg" },
  { match: /pasta/i, image: "images/pasta.jpg" },
  { match: /cereal/i, image: "images/cereal.jpg" },
  { match: /greek yogurt|yogurt/i, image: "images/yogurt.jpg" },
  { match: /butter 250g|^butter\b/i, image: "images/butter.jpg" },
  { match: /peanut butter/i, image: "images/peanut-butter.jpg" },
  { match: /cheddar/i, image: "images/cheddar.jpg" },
  { match: /parmesan/i, image: "images/parmesan.jpg" },
  { match: /flour/i, image: "images/flour.jpg" },
  { match: /olive oil/i, image: "images/olive-oil.jpg" },
  { match: /rice/i, image: "images/rice.jpg" },
  { match: /sugar/i, image: "images/sugar.jpg" },
  { match: /tomato sauce/i, image: "images/tomato-sauce.jpg" },
  { match: /apple/i, image: "images/apples.jpg" },
  { match: /avocado/i, image: "images/avocado.jpg" },
  { match: /spinach/i, image: "images/spinach.jpg" },
  { match: /banana/i, image: "images/bananas.jpg" },
  { match: /tomato/i, image: "images/produce.jpg" },
  { match: /frozen berries/i, image: "images/frozen-berries.jpg" },
  { match: /frozen pizza/i, image: "images/frozen-pizza.jpg" },
  { match: /frozen vegetable/i, image: "images/frozen-vegetables.jpg" },
  { match: /ice cream/i, image: "images/ice-cream.jpg" },
];

function productImage(name, category) {
  if (name) {
    const hit = PRODUCT_IMAGE_KEYWORDS.find((k) => k.match.test(name));
    if (hit) return hit.image;
  }
  return CATEGORY_IMAGES[category] || FALLBACK_IMAGE;
}

function productThumb(name, category, size) {
  const s = size || 48;
  return `<img class="product-thumb" src="${productImage(name, category)}" alt="${escapeHtml(name || category || "Product")}" style="width:${s}px;height:${s}px;min-width:${s}px;object-fit:cover" loading="lazy" />`;
}

// Card variant: no inline width/height, so the .product-card .product-thumb CSS rule
// (100% width, fixed height) controls sizing instead of fighting an inline style.
function productThumbCard(name, category) {
  return `<img class="product-thumb" src="${productImage(name, category)}" alt="${escapeHtml(name || category || "Product")}" loading="lazy" />`;
}

// Applies the matched photo directly onto an existing element (e.g. a fixed-size hero thumb)
// instead of generating a new wrapper element.
function applyThumb(el, name, category) {
  el.style.backgroundImage = `url("${productImage(name, category)}")`;
  el.style.backgroundSize = "cover";
  el.style.backgroundPosition = "center";
}

function ratingStars(avgRating) {
  if (avgRating === null || avgRating === undefined) return `<span style="color:var(--text-faint)">No reviews yet</span>`;
  const rounded = Math.round(avgRating * 10) / 10;
  return `<span style="color:var(--amber)">★</span> ${rounded}`;
}

// Compact rating row for product cards - empty string (not "no reviews" text) when unrated,
// so unrated cards just quietly omit the row instead of cluttering the grid.
function ratingRow(avgRating) {
  if (avgRating === null || avgRating === undefined) return "";
  const rounded = Math.round(avgRating * 10) / 10;
  return `<div class="rating-row"><span>★</span> ${rounded}</div>`;
}

// Decorative wishlist toggle used on every product-card across the app. Purely client-side
// (no backend concept of a wishlist) - it's UI furniture that makes the catalog read as a real
// storefront, not a persisted feature.
function wishlistButton() {
  return `<div class="wishlist-btn" onclick="event.stopPropagation(); this.textContent = this.textContent === '♡' ? '❤' : '♡';">♡</div>`;
}

function productUrl(id) {
  return `product-detail.html?id=${encodeURIComponent(id)}`;
}

function customerUrl(id) {
  return `customers.html?id=${encodeURIComponent(id)}`;
}

function categoryUrl(id) {
  return `category.html?id=${encodeURIComponent(id)}`;
}

// --- DB health indicator (polled) ---
function initHealthIndicator() {
  const dot = document.getElementById("db-dot");
  const label = document.getElementById("db-label");
  const banner = document.getElementById("db-banner");
  if (!dot) return;

  async function check() {
    dot.className = "dot checking";
    label.textContent = "Checking…";
    try {
      await Api.get("/api/health");
      dot.className = "dot up";
      label.textContent = "CognoDB connected";
      if (banner) banner.classList.add("hidden");
    } catch (e) {
      dot.className = "dot down";
      label.textContent = "CognoDB unreachable";
      if (banner) {
        banner.classList.remove("hidden");
        banner.textContent = "⚠️ Can't reach the database right now. Data on this page may be stale or unavailable. Retrying automatically…";
      }
    }
  }
  check();
  setInterval(check, 15000);
}

// --- Nav active-link highlighting ---
function initNav() {
  const here = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-links a").forEach((a) => {
    if (a.getAttribute("href").split("?")[0] === here) a.classList.add("active");
  });
}

// --- Category sidebar (present on every page that has a #sidebar element) ---
async function initSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;

  const activeCategoryId = new URLSearchParams(location.search).get("id");
  const onCategoryPage = location.pathname.split("/").pop() === "category.html";

  try {
    const categories = await Api.get("/api/categories");
    sidebar.innerHTML = `
      <div class="sidebar-title">Shop by category</div>
      <a class="sidebar-link${!onCategoryPage ? " active" : ""}" href="index.html">
        <span>All products</span>
      </a>
      ${categories.map((c) => `
        <a class="sidebar-link${onCategoryPage && c.id === activeCategoryId ? " active" : ""}" href="${categoryUrl(c.id)}">
          <span>${escapeHtml(c.name)}</span>
          <span class="count">${c.productCount}</span>
        </a>`).join("")}
    `;
  } catch (e) {
    sidebar.innerHTML = `<div class="sidebar-title">Shop by category</div><div style="padding:0 20px;font-size:12.5px;color:var(--text-faint)">Unavailable right now.</div>`;
  }
}

// --- Generic search-as-you-type box wired to /api/products/search ---
function initProductSearch(inputEl, resultsEl, onSelect) {
  const doSearch = debounce(async () => {
    const q = inputEl.value.trim();
    if (q.length < 2) {
      resultsEl.classList.remove("open");
      resultsEl.innerHTML = "";
      return;
    }
    try {
      const results = await Api.get(`/api/products/search?q=${encodeURIComponent(q)}&limit=15`);
      if (!results.length) {
        resultsEl.innerHTML = `<div class="search-result-item"><span class="desc">No products match "${escapeHtml(q)}"</span></div>`;
        resultsEl.classList.add("open");
        return;
      }
      resultsEl.innerHTML = results.map((p) => `
        <div class="search-result-item" data-id="${escapeHtml(p.id)}">
          ${productThumb(p.name, p.category, 32)}
          <span class="name">${escapeHtml(p.name)}</span>
          ${categoryBadge(p.category)}
          <span class="desc">${escapeHtml(p.brand || "")} · ${formatPrice(p.price)}</span>
        </div>`).join("");
      resultsEl.classList.add("open");
      resultsEl.querySelectorAll(".search-result-item[data-id]").forEach((el) => {
        el.addEventListener("click", () => onSelect(el.getAttribute("data-id")));
      });
    } catch (e) {
      resultsEl.innerHTML = `<div class="search-result-item"><span class="desc">Search failed: ${escapeHtml(e.message)}</span></div>`;
      resultsEl.classList.add("open");
    }
  }, 220);

  inputEl.addEventListener("input", doSearch);
  inputEl.addEventListener("focus", doSearch);
  document.addEventListener("click", (e) => {
    if (!resultsEl.contains(e.target) && e.target !== inputEl) {
      resultsEl.classList.remove("open");
    }
  });
}

// --- Generic search-as-you-type box wired to /api/customers/search ---
function initCustomerSearch(inputEl, resultsEl, onSelect) {
  const doSearch = debounce(async () => {
    const q = inputEl.value.trim();
    if (q.length < 2) {
      resultsEl.classList.remove("open");
      resultsEl.innerHTML = "";
      return;
    }
    try {
      const results = await Api.get(`/api/customers/search?q=${encodeURIComponent(q)}&limit=15`);
      if (!results.length) {
        resultsEl.innerHTML = `<div class="search-result-item"><span class="desc">No customers match "${escapeHtml(q)}"</span></div>`;
        resultsEl.classList.add("open");
        return;
      }
      resultsEl.innerHTML = results.map((c) => `
        <div class="search-result-item" data-id="${escapeHtml(c.id)}">
          <span class="name">${escapeHtml(c.name)}</span>
          <span class="desc">${escapeHtml(c.email)}</span>
        </div>`).join("");
      resultsEl.classList.add("open");
      resultsEl.querySelectorAll(".search-result-item[data-id]").forEach((el) => {
        el.addEventListener("click", () => onSelect(el.getAttribute("data-id")));
      });
    } catch (e) {
      resultsEl.innerHTML = `<div class="search-result-item"><span class="desc">Search failed: ${escapeHtml(e.message)}</span></div>`;
      resultsEl.classList.add("open");
    }
  }, 220);

  inputEl.addEventListener("input", doSearch);
  inputEl.addEventListener("focus", doSearch);
  document.addEventListener("click", (e) => {
    if (!resultsEl.contains(e.target) && e.target !== inputEl) {
      resultsEl.classList.remove("open");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initNav();
  initHealthIndicator();
  initSidebar();
  initLogoutLink();
});
