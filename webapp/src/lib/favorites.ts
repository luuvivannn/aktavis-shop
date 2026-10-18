import { useSyncExternalStore } from "react";

/** Favourites live on the device (localStorage). The key is the one the
 *  previous Mini App used, so nobody loses their saved items. */
const KEY = "aktavis_favorites_v1";
const listeners = new Set<() => void>();
let cache: number[] = read();

function read(): number[] {
  try {
    const arr = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(arr) ? arr.filter(Number.isInteger) : [];
  } catch {
    return [];
  }
}

function write(ids: number[]) {
  cache = ids;
  try {
    localStorage.setItem(KEY, JSON.stringify(ids));
  } catch {
    /* private mode: keep them for this session only */
  }
  listeners.forEach((fn) => fn());
}

export const favorites = {
  has: (id: number) => cache.includes(id),
  toggle(id: number): boolean {
    const on = !cache.includes(id);
    write(on ? [id, ...cache] : cache.filter((x) => x !== id));
    return on;
  },
  remove: (ids: number[]) => write(cache.filter((x) => !ids.includes(x))),
};

function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function useFavorites(): number[] {
  return useSyncExternalStore(subscribe, () => cache);
}
