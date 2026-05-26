// Catalog screen — category pills + filter sheet + product grid.

import { api } from "../api.js";
import { bindCards, productCardHtml } from "../components/product_card.js";
import {
  bindCategoryPills,
  categoryPillsHtml,
} from "../components/category_pills.js";
import { openFilterSheet } from "../components/filter_sheet.js";
import { filters } from "../state/filters.js";
import { hideBackButton, hideMainButton } from "../tg.js";

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function activeFiltersBadge() {
  const f = filters.get();
  let count = 0;
  if (f.size) count++;
  if (f.price_min != null) count++;
  if (f.price_max != null) count++;
  if (f.sort_by && f.sort_by !== "newest") count++;
  return count > 0 ? count : null;
}

export async function viewCatalog(container) {
  hideMainButton();
  hideBackButton();

  // If user picked the "Под заказ" category, route them to that screen.
  if (filters.get().category === "custom_order") {
    location.hash = "#/custom-order";
    filters.set({ category: null });
    return;
  }

  container.innerHTML = `
    <header class="header">
      <h1>AKTAVIS.EU</h1>
      <p class="hint">Оригинальные вещи · Варшава</p>
    </header>

    <div id="pills-slot"></div>

    <div class="toolbar">
      <button class="btn-filter" id="open-filters">
        ☰ Фильтры
        <span class="badge-inline" id="filters-badge"></span>
      </button>
    </div>

    <div class="grid" id="products-grid">
      <div class="loading">Загрузка…</div>
    </div>
  `;

  // Render category pills (active category from state).
  const pillsSlot = container.querySelector("#pills-slot");
  pillsSlot.innerHTML = categoryPillsHtml();
  bindCategoryPills(pillsSlot, () => render());

  // Filters button
  const filterBtn = container.querySelector("#open-filters");
  filterBtn.addEventListener("click", () => {
    openFilterSheet(() => render());
  });

  refreshFiltersBadge();

  await render();

  // ---- helpers ----
  function refreshFiltersBadge() {
    const badge = container.querySelector("#filters-badge");
    const n = activeFiltersBadge();
    if (!badge) return;
    if (n) {
      badge.textContent = String(n);
      badge.classList.add("badge-inline--visible");
    } else {
      badge.textContent = "";
      badge.classList.remove("badge-inline--visible");
    }
  }

  async function render() {
    refreshFiltersBadge();

    const grid = container.querySelector("#products-grid");
    grid.innerHTML = `<div class="loading">Загрузка…</div>`;

    const f = filters.get();
    let data;
    try {
      data = await api.listProducts({
        category: f.category ?? undefined,
        size: f.size ?? undefined,
        sort_by: f.sort_by ?? undefined,
        price_min: f.price_min ?? undefined,
        price_max: f.price_max ?? undefined,
        limit: 100,
      });
    } catch (e) {
      grid.innerHTML = `<div class="error">Не удалось загрузить каталог: ${escapeHtml(e.message)}</div>`;
      return;
    }

    if (!data.items.length) {
      grid.innerHTML = `
        <div class="empty">
          <div class="empty-icon">🪄</div>
          <h2>Ничего не нашли</h2>
          <p>Попробуйте сбросить фильтры или выбрать другую категорию.</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = data.items.map(productCardHtml).join("");
    bindCards(grid, (id) => {
      location.hash = `#/product/${id}`;
    });
  }
}
