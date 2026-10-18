import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { tg } from "./telegram";

export type Category =
  | "bags"
  | "shoes"
  | "tops"
  | "jackets"
  | "pants"
  | "accessories"
  | "custom_order"
  | "other";

export type SortBy = "newest" | "price_asc" | "price_desc";

export type ProductStatus = "pending" | "in_stock" | "reserved" | "sold" | "duplicated" | "hidden";

/** Mirrors api/schemas.py. Euros are the main currency; older posts only
 *  have złoty (and sometimes USDT). */
export interface Product {
  id: number;
  brand: string;
  name: string;
  category: Category;
  size: string | null;
  price_pln: number;
  price_usdt: number | null;
  price_eur: number | null;
  price_eur_original: number | null;
  price_pln_original: number | null;
  status: ProductStatus;
  main_photo: string | null;
  is_new: boolean;
}

export interface ProductDetail extends Product {
  condition: string | null;
  description: string | null;
  note: string | null;
  photos: string[];
}

export interface ProductList {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
}

export interface CatalogFilters {
  category: Category | null;
  size: string | null;
  sort_by: SortBy;
  price_min: number | null;
  price_max: number | null;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
  };
  if (tg?.initData) headers.Authorization = `tma ${tg.initData}`;
  const res = await fetch(path, { ...init, headers: { ...headers, ...init.headers } });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

function query(params: Record<string, string | number | null | undefined>): string {
  const out = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    out.set(key, String(value));
  }
  const s = out.toString();
  return s ? `?${s}` : "";
}

export const api = {
  listProducts: (f: CatalogFilters) =>
    request<ProductList>(
      `/api/products${query({
        category: f.category,
        size: f.size,
        sort_by: f.sort_by,
        price_min: f.price_min,
        price_max: f.price_max,
        limit: 100,
      })}`,
    ),
  getProduct: (id: number) => request<ProductDetail>(`/api/products/${id}`),
  /** Join the bot's promo audience. The server only accepts it when
   *  Telegram's signed initData says the user lets the bot message them. */
  subscribe: () => request<{ subscribed: boolean }>("/api/subscribe", { method: "POST" }),
};

export function useCatalog(filters: CatalogFilters) {
  return useQuery({
    queryKey: ["catalog", filters],
    queryFn: () => api.listProducts(filters),
    placeholderData: keepPreviousData,
  });
}

export function useProduct(id: number) {
  return useQuery({
    queryKey: ["product", id],
    queryFn: () => api.getProduct(id),
  });
}

/** Favourites: each id fetched (and cached) on its own; missing ones drop out. */
export function useProducts(ids: number[]) {
  return useQuery({
    queryKey: ["products", ids],
    queryFn: async () => {
      const settled = await Promise.allSettled(ids.map((id) => api.getProduct(id)));
      return settled.flatMap((r) => (r.status === "fulfilled" ? [r.value] : []));
    },
    enabled: ids.length > 0,
  });
}
