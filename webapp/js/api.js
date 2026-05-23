const tg = window.Telegram?.WebApp;

function authHeader() {
  if (tg && tg.initData) {
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

export const api = {
  listProducts({ category, brand, limit = 50, offset = 0 } = {}) {
    const params = new URLSearchParams({ limit, offset });
    if (category) params.set("category", category);
    if (brand) params.set("brand", brand);
    return request(`/api/products?${params}`);
  },

  getProduct(id) {
    return request(`/api/products/${id}`);
  },

  listBrands() {
    return request(`/api/products/brands`);
  },

  searchProducts(q) {
    return request(`/api/products/search?q=${encodeURIComponent(q)}`);
  },

  createOrder(payload) {
    return request(`/api/orders`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  myOrders() {
    return request(`/api/orders/my`);
  },

  me() {
    return request(`/api/me`);
  },
};
