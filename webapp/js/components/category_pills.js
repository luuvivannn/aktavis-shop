// Horizontal scrolling category selector at the top of the catalog.

import { filters } from "../state/filters.js";
import { haptic } from "../tg.js";

// Ordered list of categories shown in the pills bar.
// `null` means "Все" (no filter).
export const CATEGORIES = [
  { value: null,           label: "Все" },
  { value: "shoes",        label: "Обувь" },
  { value: "tops",         label: "Худи / Футболки" },
  { value: "jackets",      label: "Куртки" },
  { value: "pants",        label: "Шорты/Штаны" },
  { value: "bags",         label: "Сумки" },
  { value: "accessories",  label: "Аксессуары" },
  { value: "custom_order", label: "Под заказ" },
];

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function categoryPillsHtml() {
  const active = filters.get().category;
  return `
    <div class="category-pills" role="tablist">
      ${CATEGORIES.map((c) => `
        <button
          type="button"
          class="pill ${active === c.value ? "pill--active" : ""}"
          data-cat="${c.value ?? ""}"
        >${escapeHtml(c.label)}</button>
      `).join("")}
    </div>
  `;
}

export function bindCategoryPills(root, onChange) {
  root.querySelectorAll(".pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      const value = btn.dataset.cat || null;
      if (filters.get().category === value) return;
      filters.set({ category: value, size: null });
      // visual update
      root.querySelectorAll(".pill").forEach((p) =>
        p.classList.toggle("pill--active", p === btn)
      );
      haptic("light");
      onChange(value);
    });
  });
}
