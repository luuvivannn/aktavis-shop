// Product detail screen.
//
// Differences from the old design:
//   - Heart icon (top-right of header) toggles favourite, no cart logic.
//   - The MainButton opens t.me/aktavis_eu with a pre-filled message that
//     includes brand, name, size, AND the product photo URL — Telegram
//     auto-renders the URL as a photo preview in the input box.

import { api } from "../api.js";
import { favorites } from "../state/favorites.js";
import {
  haptic,
  hideMainButton,
  setBackButton,
  setMainButton,
  tg,
} from "../tg.js";

const SELLER_USERNAME = "aktavis_eu";

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatPrice(pln, usdt, eur) {
  // EUR is the active currency. Legacy products without € fall back to zł.
  if (eur) return `${Number(eur).toLocaleString("pl-PL")}€`;
  if (pln) {
    let s = `${Number(pln).toLocaleString("pl-PL")} zł`;
    if (usdt) s += ` / ${usdt} USDT`;
    return s;
  }
  return "—";
}

function absoluteUrl(path) {
  if (!path) return null;
  if (/^https?:\/\//.test(path)) return path;
  return new URL(path, window.location.origin).href;
}

function buildSellerLink(product) {
  const size = product.size || "—";
  const photoUrl = absoluteUrl(product.main_photo);
  const lines = [
    `Привет! Хочу купить ${product.brand} ${product.name}, размер ${size}`,
  ];
  if (photoUrl) lines.push(photoUrl);
  const text = lines.join("\n");
  return `https://t.me/${SELLER_USERNAME}?text=${encodeURIComponent(text)}`;
}

export async function viewProduct(container, id) {
  hideMainButton();

  container.innerHTML = `<div class="loading">Загрузка…</div>`;

  let p;
  try {
    p = await api.getProduct(id);
  } catch (e) {
    container.innerHTML = `<div class="error">Не удалось загрузить товар: ${escapeHtml(e.message)}</div>`;
    setBackButton(() => history.back());
    return;
  }

  const fav = favorites.has(p.id);

  container.innerHTML = `
    <div class="product">
      <div class="gallery">
        ${p.is_new ? `<span class="badge-new badge-new--big">NEW</span>` : ""}
        <button class="heart heart--big ${fav ? "heart--on" : ""}" id="product-heart" aria-label="В избранное">
          ${fav ? "♥" : "♡"}
        </button>
        ${p.photos.map((src, i) => `
          <img class="gallery-img ${i === 0 ? "active" : ""}" src="${escapeHtml(src)}" data-idx="${i}" alt="" />
        `).join("")}
        ${p.photos.length > 1 ? `
          <div class="gallery-dots">
            ${p.photos.map((_, i) => `<span class="dot ${i === 0 ? "active" : ""}" data-idx="${i}"></span>`).join("")}
          </div>
        ` : ""}
      </div>

      <div class="product-body">
        <div class="brand-line">${escapeHtml(p.brand)}</div>
        <h1 class="product-name">${escapeHtml(p.name)}</h1>

        ${p.size ? `<div class="row"><span class="label">Размер</span><span>${escapeHtml(p.size)}</span></div>` : ""}
        ${p.condition ? `<div class="row"><span class="label">Состояние</span><span>${escapeHtml(p.condition)}</span></div>` : ""}
        ${p.note ? `<div class="note">⚠️ ${escapeHtml(p.note)}</div>` : ""}

        <div class="price-big">${formatPrice(p.price_pln, p.price_usdt, p.price_eur)}</div>

        ${p.description ? `<pre class="desc">${escapeHtml(p.description)}</pre>` : ""}
      </div>
    </div>
  `;

  // Gallery
  const imgs = container.querySelectorAll(".gallery-img");
  const dots = container.querySelectorAll(".dot");
  let current = 0;

  function setActive(i) {
    if (i < 0 || i >= imgs.length) return;
    imgs[current].classList.remove("active");
    dots[current]?.classList.remove("active");
    current = i;
    imgs[current].classList.add("active");
    dots[current]?.classList.add("active");
  }
  dots.forEach((d, i) => d.addEventListener("click", () => setActive(i)));

  if (imgs.length > 1) {
    let startX = 0;
    const gallery = container.querySelector(".gallery");
    gallery.addEventListener("touchstart", (e) => {
      startX = e.touches[0].clientX;
    }, { passive: true });
    gallery.addEventListener("touchend", (e) => {
      const dx = e.changedTouches[0].clientX - startX;
      if (Math.abs(dx) < 40) return;
      if (dx < 0) setActive(current + 1);
      else setActive(current - 1);
    }, { passive: true });
  }

  // Heart
  const heart = container.querySelector("#product-heart");
  heart.addEventListener("click", () => {
    const nowFav = favorites.toggle(p.id);
    haptic("light");
    heart.classList.toggle("heart--on", nowFav);
    heart.innerHTML = nowFav ? "♥" : "♡";
  });

  // Main button → write to seller
  const sellerLink = buildSellerLink(p);
  setMainButton("Написать продавцу", () => {
    haptic("medium");
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(sellerLink);
    } else {
      window.open(sellerLink, "_blank");
    }
  });

  setBackButton(() => history.back());
}
