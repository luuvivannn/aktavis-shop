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

  container.innerHTML = `
    <header class="header">
      <div class="brand-header">
        <div class="brand-logo">
          <svg viewBox="0 0 240 240" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M180 68L155 175c-1.7 7.5-6.3 9.4-12.7 5.8l-35-25.8-16.9 16.3c-1.9 1.9-3.4 3.4-7 3.4l2.5-35.4 64.5-58.3c2.8-2.5-.6-3.9-4.3-1.4l-79.7 50.2-34.3-10.7c-7.5-2.3-7.6-7.5 1.5-11.1l133.7-51.6c6.2-2.3 11.7 1.5 9.7 11.6z" fill="white"/>
          </svg>
        </div>
        <h1>AKTAVIS.EU</h1>
      </div>
      <p class="hint">Оригинальные вещи · Самая быстрая доставка в любую точку мира</p>
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
    const f = filters.get();

    // Special "Под заказ" category — show info banner instead of products.
    if (f.category === "custom_order") {
      grid.innerHTML = `
        <div class="custom-order-inline">
          <img src="img/custom_order_banner.jpg" alt="Под заказ" />
          <p><b>Привезу вещь любой сложности в самые кратчайшие сроки ‼️</b></p>
          <p><b>Намного ниже рынка!!!</b></p>
        </div>
      `;
      return;
    }

    grid.innerHTML = `<div class="loading">Загрузка…</div>`;

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
