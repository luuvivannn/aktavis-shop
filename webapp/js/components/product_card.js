// Renders a single product card (catalog grid item).
//
// Slots:
//   top-left  → NEW badge (if product.is_new)
//   top-right → heart icon (filled if product is in favorites)
//   center    → main photo (1:1)
//   bottom    → brand · name · price
//
// Click anywhere on the card → product detail page.
// Click on the heart       → toggles favorite (event doesn't bubble).

import { favorites } from "../state/favorites.js";
import { haptic } from "../tg.js";

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatPrice(pln, usdt, eur, plnOrig = null, eurOrig = null) {
  // EUR is the active currency. Legacy products without € fall back to zł.
  if (eur) {
    const cur = `${Number(eur).toLocaleString("pl-PL")}€`;
    if (eurOrig && eurOrig > eur)
      return `<span class="price-original">${Number(eurOrig).toLocaleString("pl-PL")}€</span> <span class="price-sale">${cur}</span>`;
    return cur;
  }
  if (pln) {
    const cur = `${Number(pln).toLocaleString("pl-PL")} zł`;
    if (plnOrig && plnOrig > pln)
      return `<span class="price-original">${Number(plnOrig).toLocaleString("pl-PL")} zł</span> <span class="price-sale">${cur}</span>`;
    let s = cur;
    if (usdt) s += ` / ${usdt} USDT`;
    return s;
  }
  return "—";
}

export function productCardHtml(p) {
  const photo = p.main_photo || "";
  const fav = favorites.has(p.id);
  const brand = escapeHtml(p.brand);
  const name = escapeHtml(p.name);
  // Brand + name on a single line, one colour (see .card-title).
  const title = brand
    ? `<span class="card-brand">${brand}</span> <span class="card-name">${name}</span>`
    : `<span class="card-name">${name}</span>`;
  return `
    <article class="card" data-id="${p.id}">
      <div class="card-photo-wrap">
        ${photo
          ? `<img class="card-photo" src="${escapeHtml(photo)}" loading="lazy" alt="${escapeHtml(p.brand)}" />`
          : `<div class="card-photo card-photo--empty"></div>`
        }
        ${p.is_new ? `<span class="badge-new">NEW</span>` : ""}
        <button class="heart ${fav ? "heart--on" : ""}" data-fav="${p.id}" aria-label="В избранное">
          ${fav ? "♥" : "♡"}
        </button>
      </div>
      <div class="card-body">
        <div class="card-title">${title}</div>
        <div class="card-price">${formatPrice(p.price_pln, p.price_usdt, p.price_eur, p.price_pln_original, p.price_eur_original)}</div>
      </div>
    </article>
  `;
}

/**
 * Wire up card and heart click handlers within a container.
 *
 * @param {HTMLElement} root      element containing one or more .card nodes
 * @param {function} onOpen       called with product id when card body is tapped
 */
export function bindCards(root, onOpen) {
  root.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("click", (e) => {
      // Heart clicks bubble up — ignore them here, they're handled below.
      if (e.target.closest(".heart")) return;
      haptic("light");
      onOpen(Number(card.dataset.id));
    });
  });

  root.querySelectorAll(".heart").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = Number(btn.dataset.fav);
      const nowFav = favorites.toggle(id);
      haptic("light");
      btn.classList.toggle("heart--on", nowFav);
      btn.innerHTML = nowFav ? "♥" : "♡";
    });
  });
}
