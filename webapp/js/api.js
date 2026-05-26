// Lightweight wrapper around fetch() that adds Telegram auth + JSON handling.
//
// The new Mini App only needs read endpoints (catalog/product/search) —
// orders moved out to direct DMs with the seller, so the API surface
// here is small.

const tg = window.Telegram?.WebApp;

function authHeader() {
  if (tg?.initData) {
    return { Authorization: `tma ${tg.initData}` };
  }
  return {};
}

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
    ...authHeader(),
    ...(options.headers || {}),
  };

  const res = await fetch(path, { ...options, headers });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch (_) { /* not JSON */ }
    throw new Error(detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

function buildQuery(params) {
  const out = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    out.set(key, String(value));
  }
  return out.toString();
}

export const api = {
  /**
   * List catalog products with filters.
   *
   * @param {object} opts
   * @param {string} [opts.category]    one of ProductCategory enum values
   * @param {string} [opts.size]        substring match against product.size
   * @param {string} [opts.sort_by]     "newest" | "price_asc" | "price_desc"
   * @param {number} [opts.price_min]   PLN, inclusive
   * @param {number} [opts.price_max]   PLN, inclusive
   * @param {number} [opts.limit=100]
   * @param {number} [opts.offset=0]
   */
  listProducts(opts = {}) {
    const q = buildQuery({
      category: opts.category,
      size: opts.size,
      sort_by: opts.sort_by,
      price_min: opts.price_min,
      price_max: opts.price_max,
      limit: opts.limit ?? 100,
      offset: opts.offset ?? 0,
    });
    return request(`/api/products${q ? "?" + q : ""}`);
  },

  getProduct(id) {
    return request(`/api/products/${id}`);
  },

  searchProducts(q) {
    return request(`/api/products/search?q=${encodeURIComponent(q)}`);
  },

  /** Fetch many products by ID in parallel. Used by the favorites view. */
  async getProducts(ids) {
    if (!ids || !ids.length) return [];
    const settled = await Promise.allSettled(ids.map((id) => this.getProduct(id)));
    return settled
      .filter((r) => r.status === "fulfilled")
      .map((r) => r.value);
  },
};
