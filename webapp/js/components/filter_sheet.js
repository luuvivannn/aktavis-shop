// Bottom-sheet filter panel — opens from the "Фильтры" button on the
// catalog. Lets the user pick size, price range, and sort order.

import { filters } from "../state/filters.js";
import { haptic } from "../tg.js";

const CLOTHING_SIZES = ["XS", "S", "M", "L", "XL", "XXL"];
const SHOE_SIZES = ["36", "37", "38", "39", "40", "41", "42", "43", "44", "45", "46"];

function sizesForCategory(category) {
  if (category === "shoes") return SHOE_SIZES;
  if (category === "tops" || category === "jackets" || category === "pants") {
    return CLOTHING_SIZES;
  }
  return null; // hide size filter
}

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function openFilterSheet(onApply) {
  const current = filters.get();
  const sizes = sizesForCategory(current.category);

  const sheet = document.createElement("div");
  sheet.className = "sheet-overlay";
  sheet.innerHTML = `
    <div class="sheet">
      <div class="sheet-handle"></div>
      <header class="sheet-header">
        <h2>Фильтры</h2>
        <button class="sheet-close" aria-label="Закрыть">✕</button>
      </header>

      <section class="sheet-section">
        <h3>Сортировка</h3>
        <div class="pill-row">
          <button class="pill ${current.sort_by === "newest" ? "pill--active" : ""}" data-sort="newest">Новизна</button>
          <button class="pill ${current.sort_by === "price_asc" ? "pill--active" : ""}" data-sort="price_asc">Цена ↑</button>
          <button class="pill ${current.sort_by === "price_desc" ? "pill--active" : ""}" data-sort="price_desc">Цена ↓</button>
        </div>
      </section>

      ${sizes ? `
        <section class="sheet-section">
          <h3>Размер</h3>
          <div class="pill-row">
            <button class="pill ${!current.size ? "pill--active" : ""}" data-size="">Любой</button>
            ${sizes.map((s) => `
              <button class="pill ${current.size === s ? "pill--active" : ""}" data-size="${escapeHtml(s)}">${escapeHtml(s)}</button>
            `).join("")}
          </div>
        </section>
      ` : ""}

      <section class="sheet-section">
        <h3>Цена, €</h3>
        <div class="price-range">
          <input type="number" class="price-input" id="price-min" placeholder="от" min="0" value="${current.price_min ?? ""}" />
          <span>—</span>
          <input type="number" class="price-input" id="price-max" placeholder="до" min="0" value="${current.price_max ?? ""}" />
        </div>
      </section>

      <div class="sheet-actions">
        <button class="btn-secondary" id="filter-reset">Сбросить</button>
        <button class="btn-primary" id="filter-apply">Применить</button>
      </div>
    </div>
  `;

  document.body.appendChild(sheet);
  document.body.classList.add("no-scroll");

  // Local working state (only commit on Apply).
  let pending = { ...current };

  // Sort selection
  sheet.querySelectorAll("[data-sort]").forEach((btn) => {
    btn.addEventListener("click", () => {
      pending.sort_by = btn.dataset.sort;
      sheet.querySelectorAll("[data-sort]").forEach((b) =>
        b.classList.toggle("pill--active", b === btn)
      );
      haptic("light");
    });
  });

  // Size selection
  sheet.querySelectorAll("[data-size]").forEach((btn) => {
    btn.addEventListener("click", () => {
      pending.size = btn.dataset.size || null;
      sheet.querySelectorAll("[data-size]").forEach((b) =>
        b.classList.toggle("pill--active", b === btn)
      );
      haptic("light");
    });
  });

  function close() {
    sheet.remove();
    document.body.classList.remove("no-scroll");
  }

  sheet.querySelector(".sheet-close").addEventListener("click", close);
  sheet.addEventListener("click", (e) => {
    if (e.target === sheet) close();
  });

  sheet.querySelector("#filter-reset").addEventListener("click", () => {
    pending = {
      category: pending.category,
      size: null,
      sort_by: "newest",
      price_min: null,
      price_max: null,
    };
    filters.set(pending);
    close();
    onApply();
    haptic("medium");
  });

  sheet.querySelector("#filter-apply").addEventListener("click", () => {
    const min = sheet.querySelector("#price-min").value;
    const max = sheet.querySelector("#price-max").value;
    pending.price_min = min ? Number(min) : null;
    pending.price_max = max ? Number(max) : null;
    filters.set(pending);
    close();
    onApply();
    haptic("medium");
  });
}
