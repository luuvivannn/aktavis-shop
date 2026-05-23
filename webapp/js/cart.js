const STORAGE_KEY = "aktavis_cart_v1";
const listeners = new Set();

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function save(items) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  for (const fn of listeners) {
    try { fn(items); } catch (e) { console.error(e); }
  }
}

export const cart = {
  list() {
    return load();
  },

  has(productId) {
    return load().some(i => i.product_id === productId);
  },

  add(productId, quantity = 1) {
    const items = load();
    const existing = items.find(i => i.product_id === productId);
    if (existing) {
      existing.quantity += quantity;
    } else {
      items.push({ product_id: productId, quantity });
    }
    save(items);
  },

  remove(productId) {
    save(load().filter(i => i.product_id !== productId));
  },

  clear() {
    save([]);
  },

  count() {
    return load().reduce((sum, i) => sum + i.quantity, 0);
  },

  onChange(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
};
