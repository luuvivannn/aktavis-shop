// In-memory state for the active catalog filters.
//
// Persists for the lifetime of the Mini App session (resets on close)
// because we want users to start with a clean catalog every time.

const state = {
  category: null,         // null = "Все"
  size: null,             // null = any
  sort_by: "newest",      // "newest" | "price_asc" | "price_desc"
  price_min: null,
  price_max: null,
};

const listeners = new Set();

function notify() {
  for (const fn of listeners) {
    try { fn(state); } catch (e) { console.error(e); }
  }
}

export const filters = {
  /** Returns a shallow copy of the current filter values. */
  get() {
    return { ...state };
  },

  /** Update one or more filter fields. Pass `null` to clear a field. */
  set(updates) {
    let changed = false;
    for (const [key, value] of Object.entries(updates)) {
      if (!(key in state)) continue;
      if (state[key] !== value) {
        state[key] = value;
        changed = true;
      }
    }
    if (changed) notify();
  },

  reset() {
    state.category = null;
    state.size = null;
    state.sort_by = "newest";
    state.price_min = null;
    state.price_max = null;
    notify();
  },

  /** Subscribe to changes. Returns an unsubscribe function. */
  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
};
