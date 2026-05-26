// Favourites are stored client-side in localStorage. No server sync.
//
// Shape: a sorted array of integer product IDs, persisted as JSON.

const STORAGE_KEY = "aktavis_favorites_v1";

const listeners = new Set();

function readRaw() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return [];
    return arr.filter((x) => Number.isInteger(x));
  } catch {
    return [];
  }
}

function writeRaw(ids) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch (e) {
    console.error("Failed to persist favorites:", e);
  }
  for (const fn of listeners) {
    try { fn(ids); } catch (e) { console.error(e); }
  }
}

export const favorites = {
  /** Returns a defensive copy of the favourite product IDs. */
  list() {
    return readRaw().slice();
  },

  count() {
    return readRaw().length;
  },

  has(productId) {
    return readRaw().includes(Number(productId));
  },

  add(productId) {
    const id = Number(productId);
    if (!Number.isInteger(id)) return;
    const ids = readRaw();
    if (ids.includes(id)) return;
    ids.push(id);
    writeRaw(ids);
  },

  remove(productId) {
    const id = Number(productId);
    const ids = readRaw().filter((x) => x !== id);
    writeRaw(ids);
  },

  toggle(productId) {
    if (this.has(productId)) {
      this.remove(productId);
      return false;
    }
    this.add(productId);
    return true;
  },

  clear() {
    writeRaw([]);
  },

  /** Subscribe to changes. Returns an unsubscribe function. */
  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
};
