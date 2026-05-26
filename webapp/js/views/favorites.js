// Favourites screen — same grid layout as catalog, sourced from
// localStorage instead of an API query.

import { api } from "../api.js";
import { bindCards, productCardHtml } from "../components/product_card.js";
import { favorites } from "../state/favorites.js";
import { hideBackButton, hideMainButton } from "../tg.js";

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export async function viewFavorites(container) {
  hideMainButton();
  hideBackButton();

  const ids = favorites.list();

  if (!ids.length) {
    container.innerHTML = `
      <header class="header">
        <h1>❤ Избранное</h1>
      </header>
      <div class="empty">
        <div class="empty-icon">🤍</div>
        <h2>Пока пусто</h2>
        <p>Открой каталог и нажми на сердечко рядом с товаром,
        чтобы сохранить его сюда.</p>
        <button class="btn-primary" id="go-catalog">К каталогу</button>
      </div>
    `;
    container.querySelector("#go-catalog").addEventListener("click", () => {
      location.hash = "#/catalog";
    });
    return;
  }

  container.innerHTML = `
    <header class="header">
      <h1>❤ Избранное</h1>
      <p class="hint">${ids.length} ${pluralRu(ids.length, "товар", "товара", "товаров")}</p>
    </header>
    <div class="grid" id="favorites-grid">
      <div class="loading">Загрузка…</div>
    </div>
  `;

  const grid = container.querySelector("#favorites-grid");

  let products;
  try {
    products = await api.getProducts(ids);
  } catch (e) {
    grid.innerHTML = `<div class="error">Не удалось загрузить: ${escapeHtml(e.message)}</div>`;
    return;
  }

  // Prune any IDs that no longer exist (e.g., product deleted).
  const liveIds = new Set(products.map((p) => p.id));
  for (const stale of ids) {
    if (!liveIds.has(stale)) favorites.remove(stale);
  }

  if (!products.length) {
    grid.innerHTML = `
      <div class="empty">
        <p>Все товары из избранного больше не доступны.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = products.map(productCardHtml).join("");
  bindCards(grid, (id) => {
    location.hash = `#/product/${id}`;
  });
}

function pluralRu(n, one, few, many) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return many;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
}
