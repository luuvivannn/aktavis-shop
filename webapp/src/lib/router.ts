import { useSyncExternalStore } from "react";

/** Hash routes, so Telegram's back button and deep links stay simple:
 *  #/ · #/product/42 · #/favorites · #/custom-order · #/about */
export type Route =
  | { name: "catalog" }
  | { name: "product"; id: number }
  | { name: "favorites" }
  | { name: "custom-order" }
  | { name: "about" };

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, "") || "/";
  const product = path.match(/^\/product\/(\d+)$/);
  if (product) return { name: "product", id: Number(product[1]) };
  if (path === "/favorites") return { name: "favorites" };
  if (path === "/custom-order") return { name: "custom-order" };
  if (path === "/about") return { name: "about" };
  return { name: "catalog" };
}

// Whether the user has moved inside the app. A product opened straight
// from a Direct Link has nothing to go back to, so «back» means the catalog.
let navigated = false;

export function navigate(path: string) {
  navigated = true;
  location.hash = path;
}

export function goBack() {
  if (navigated) history.back();
  else history.replaceState(null, "", "#/");
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

export function routeKey(route: Route): string {
  return route.name === "product" ? `product/${route.id}` : route.name;
}

function subscribe(fn: () => void) {
  window.addEventListener("hashchange", fn);
  return () => window.removeEventListener("hashchange", fn);
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => location.hash);
  return parseRoute(hash);
}

/** Direct Link parameter → route: p_42, favorites, about, custom_order. */
export function routeFromStartParam(param: string | undefined): string | null {
  if (!param) return null;
  const product = param.match(/^p_(\d+)$/);
  if (product) return `/product/${product[1]}`;
  if (param === "favorites") return "/favorites";
  if (param === "about") return "/about";
  if (param === "custom_order" || param === "custom-order") return "/custom-order";
  return null;
}
