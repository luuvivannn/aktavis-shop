import type { Product } from "./api";

type Prices = Pick<
  Product,
  "price_eur" | "price_eur_original" | "price_pln" | "price_pln_original" | "price_usdt"
>;

function amount(n: number): string {
  return Number(n).toLocaleString("pl-PL");
}

/** The price to show: euros, or złoty for older posts that have no €.
 *  `original` is the old price when the item was marked down. */
export function mainPrice(p: Prices): { current: string; original: string | null } | null {
  if (p.price_eur) {
    const original =
      p.price_eur_original && p.price_eur_original > p.price_eur ? `${amount(p.price_eur_original)}€` : null;
    return { current: `${amount(p.price_eur)}€`, original };
  }
  if (p.price_pln) {
    const original =
      p.price_pln_original && p.price_pln_original > p.price_pln
        ? `${amount(p.price_pln_original)} zł`
        : null;
    return { current: `${amount(p.price_pln)} zł`, original };
  }
  return null;
}

/** USDT under a złoty price, as the old posts gave it. */
export function secondaryPrice(p: Prices): string | null {
  if (!p.price_eur && p.price_pln && p.price_usdt) return `${amount(p.price_usdt)} USDT`;
  return null;
}

/** Brand may be blank (an unrecognised brand), so no double space. */
export function productTitle(p: Pick<Product, "brand" | "name">): string {
  return [p.brand, p.name].filter(Boolean).join(" ");
}
