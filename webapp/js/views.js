import { api } from "./api.js";
import { cart } from "./cart.js";
import {
  currentUser,
  haptic,
  hideBackButton,
  hideMainButton,
  hideMainProgress,
  notify,
  setBackButton,
  setMainButton,
  showAlert,
  showMainProgress,
  tg,
} from "./tg.js";

const STATUS_LABELS = {
  new: "🟡 Новый",
  confirmed: "🟢 Подтверждён",
  awaiting_payment: "💳 Ждёт оплаты",
  paid: "✅ Оплачен",
  shipped: "📦 Отправлен",
  delivered: "🏁 Доставлен",
  cancelled: "❌ Отменён",
};

const DELIVERY_LABELS = {
  courier_warsaw: "🚚 Курьер по Варшаве",
  europe: "✈️ Европа",
  worldwide: "🌍 Весь мир",
  pickup: "🏬 Самовывоз",
};

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatPrice(pln, usdt) {
  let s = `${Number(pln).toLocaleString("pl-PL")} zł`;
  if (usdt) s += ` / ${usdt} USDT`;
  return s;
}

function productCardHtml(p) {
  const photo = p.main_photo || "";
  return `
    <article class="card" data-id="${p.id}">
      ${photo ? `<img class="card-photo" src="${escapeHtml(photo)}" loading="lazy" alt="${escapeHtml(p.brand)}" />` : `<div class="card-photo"></div>`}
      <div class="card-body">
        <div class="card-brand">${escapeHtml(p.brand)}</div>
        <div class="card-name">${escapeHtml(p.name)}</div>
        <div class="card-meta">${p.size ? "Размер " + escapeHtml(p.size) : "&nbsp;"}</div>
        <div class="card-price">${formatPrice(p.price_pln, p.price_usdt)}</div>
      </div>
    </article>
  `;
}

// ─────────────────────────────────────────
// CATALOG
// ─────────────────────────────────────────
export async function viewCatalog(container) {
  hideMainButton();
  hideBackButton();

  container.innerHTML = `<div class="loading">Загрузка каталога…</div>`;

  let data, brands;
  try {
    [data, brands] = await Promise.all([
      api.listProducts({ limit: 100 }),
      api.listBrands(),
    ]);
  } catch (e) {
    container.innerHTML = `<div class="error">Не удалось загрузить каталог: ${escapeHtml(e.message)}</div>`;
    return;
  }

  if (data.items.length === 0) {
    container.innerHTML = `
      <div class="empty">
        <div class="empty-icon">🪄</div>
        <h2>Пока пусто</h2>
        <p>Скоро здесь появятся товары.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <header class="header">
      <h1>AKTAVIS.EU</h1>
      <p class="hint">Оригинальные вещи · Варшава</p>
    </header>

    <div class="brands">
      <button class="chip active" data-brand="">Все</button>
      ${brands.map(b => `<button class="chip" data-brand="${escapeHtml(b)}">${escapeHtml(b)}</button>`).join("")}
    </div>

    <div class="grid" id="products-grid">
      ${data.items.map(productCardHtml).join("")}
    </div>
  `;

  const grid = container.querySelector("#products-grid");

  container.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", async () => {
      container.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      haptic("light");

      const brand = chip.dataset.brand || undefined;
      grid.innerHTML = `<div class="loading">…</div>`;
      try {
        const filtered = await api.listProducts({ brand, limit: 100 });
        if (filtered.items.length === 0) {
          grid.innerHTML = `<div class="empty"><p>Ничего не нашли</p></div>`;
        } else {
          grid.innerHTML = filtered.items.map(productCardHtml).join("");
          bindCardClicks(grid);
        }
      } catch (e) {
        grid.innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
      }
    });
  });

  bindCardClicks(grid);
}

function bindCardClicks(root) {
  root.querySelectorAll(".card").forEach(card => {
    card.addEventListener("click", () => {
      haptic("light");
      location.hash = `#/product/${card.dataset.id}`;
    });
  });
}

// ─────────────────────────────────────────
// PRODUCT DETAIL
// ─────────────────────────────────────────
export async function viewProduct(container, id) {
  container.innerHTML = `<div class="loading">Загрузка…</div>`;

  let p;
  try {
    p = await api.getProduct(id);
  } catch (e) {
    container.innerHTML = `<div class="error">Не удалось загрузить товар: ${escapeHtml(e.message)}</div>`;
    return;
  }

  container.innerHTML = `
    <div class="product">
      <div class="gallery">
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

        <div class="price-big">${formatPrice(p.price_pln, p.price_usdt)}</div>

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

  // Buttons
  const refreshMainButton = () => {
    const inCart = cart.has(p.id);
    if (inCart) {
      setMainButton("✓ В корзине — перейти", () => {
        location.hash = "#/cart";
      });
    } else {
      setMainButton("В корзину", () => {
        cart.add(p.id, 1);
        haptic("medium");
        refreshMainButton();
      });
    }
  };
  refreshMainButton();

  setBackButton(() => history.back());
}

// ─────────────────────────────────────────
// CART
// ─────────────────────────────────────────
export async function viewCart(container) {
  hideBackButton();
  const items = cart.list();

  if (items.length === 0) {
    container.innerHTML = `
      <div class="empty">
        <div class="empty-icon">🧺</div>
        <h2>Корзина пуста</h2>
        <p>Откройте каталог и добавьте что-нибудь интересное.</p>
        <button class="btn" id="go-catalog">К каталогу</button>
      </div>
    `;
    container.querySelector("#go-catalog").addEventListener("click", () => {
      location.hash = "#/catalog";
    });
    hideMainButton();
    return;
  }

  container.innerHTML = `<div class="loading">…</div>`;

  let products;
  try {
    products = await Promise.all(
      items.map(i => api.getProduct(i.product_id).catch(() => null))
    );
  } catch (e) {
    container.innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
    return;
  }

  const rows = items
    .map((cartItem, idx) => ({ ...cartItem, product: products[idx] }))
    .filter(x => x.product);

  // remove items that disappeared (e.g., already sold)
  if (rows.length !== items.length) {
    const validIds = new Set(rows.map(r => r.product.id));
    items.forEach(i => {
      if (!validIds.has(i.product_id)) cart.remove(i.product_id);
    });
  }

  let totalPln = 0;
  let totalUsdt = 0;
  rows.forEach(r => {
    totalPln += r.product.price_pln * r.quantity;
    if (r.product.price_usdt) totalUsdt += r.product.price_usdt * r.quantity;
  });

  container.innerHTML = `
    <header class="header">
      <h1>🧺 Корзина</h1>
    </header>

    <div class="cart-list">
      ${rows.map(r => `
        <div class="cart-row" data-id="${r.product.id}">
          ${r.product.main_photo ? `<img class="cart-thumb" src="${escapeHtml(r.product.main_photo)}" />` : `<div class="cart-thumb"></div>`}
          <div class="cart-info">
            <div class="card-brand">${escapeHtml(r.product.brand)}</div>
            <div class="card-name">${escapeHtml(r.product.name)}</div>
            <div class="card-meta">${r.product.size ? "Размер " + escapeHtml(r.product.size) : ""} ${r.quantity > 1 ? "· ×" + r.quantity : ""}</div>
            <div class="card-price">${formatPrice(r.product.price_pln, r.product.price_usdt)}</div>
          </div>
          <button class="remove" data-remove="${r.product.id}" aria-label="Удалить">✕</button>
        </div>
      `).join("")}
    </div>

    <div class="cart-total">
      <div class="row"><span>Итого</span><strong>${formatPrice(totalPln, totalUsdt)}</strong></div>
    </div>
  `;

  container.querySelectorAll("[data-remove]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = Number(btn.dataset.remove);
      cart.remove(id);
      haptic("light");
      viewCart(container);
    });
  });

  container.querySelectorAll(".cart-row").forEach(row => {
    row.addEventListener("click", () => {
      location.hash = `#/product/${row.dataset.id}`;
    });
  });

  setMainButton("Оформить заказ", () => {
    location.hash = "#/checkout";
  });
}

// ─────────────────────────────────────────
// CHECKOUT
// ─────────────────────────────────────────
export async function viewCheckout(container) {
  const items = cart.list();
  if (items.length === 0) {
    location.hash = "#/cart";
    return;
  }

  const user = currentUser() || {};
  const defaultName = [user.first_name, user.last_name].filter(Boolean).join(" ");

  container.innerHTML = `
    <header class="header">
      <h1>Оформление</h1>
      <p class="hint">Менеджер свяжется с вами после отправки заказа.</p>
    </header>

    <form class="form" id="checkout-form" onsubmit="return false;">
      <label class="field">
        <span>Ваше имя</span>
        <input name="full_name" type="text" value="${escapeHtml(defaultName)}" required maxlength="200" />
      </label>

      <label class="field">
        <span>Телефон / контакт</span>
        <input name="phone" type="tel" placeholder="+48 ..." maxlength="50" />
      </label>

      <fieldset class="field">
        <legend>Способ доставки</legend>
        <label><input type="radio" name="delivery_method" value="courier_warsaw" checked /> 🚚 Курьер по Варшаве</label>
        <label><input type="radio" name="delivery_method" value="europe" /> ✈️ Европа</label>
        <label><input type="radio" name="delivery_method" value="worldwide" /> 🌍 Весь мир</label>
        <label><input type="radio" name="delivery_method" value="pickup" /> 🏬 Самовывоз (Варшава)</label>
      </fieldset>

      <label class="field">
        <span>Адрес доставки</span>
        <textarea name="delivery_address" rows="2" placeholder="Улица, дом, квартира, индекс"></textarea>
      </label>

      <label class="field">
        <span>Комментарий</span>
        <textarea name="comment" rows="2" maxlength="1000" placeholder="Опционально"></textarea>
      </label>

      <div class="error-box" id="checkout-error"></div>
    </form>
  `;

  const form = container.querySelector("#checkout-form");
  const errorBox = container.querySelector("#checkout-error");

  async function submit() {
    if (!tg?.initData) {
      const unsafeKeys = Object.keys(tg?.initDataUnsafe || {});
      const debug = [
        `SDK: ${tg ? "yes" : "no"}`,
        `Platform: ${tg?.platform || "—"}`,
        `Version: ${tg?.version || "—"}`,
        `Color: ${tg?.colorScheme || "—"}`,
        `Viewport: ${tg?.viewportHeight || "?"}px`,
        `initData len: ${tg?.initData?.length || 0}`,
        `unsafe keys: ${unsafeKeys.join(",") || "(none)"}`,
        `unsafe.user: ${tg?.initDataUnsafe?.user ? "yes" : "no"}`,
        `TWP: ${typeof window.TelegramWebviewProxy}`,
        `hash len: ${location.hash.length}`,
        `path: ${location.pathname}`,
      ].join("\n");
      showAlert(
        "Telegram не передал авторизацию.\n\nDebug:\n" + debug
      );
      notify("error");
      return;
    }

    const data = new FormData(form);
    const fullName = (data.get("full_name") || "").toString().trim();

    if (!fullName) {
      errorBox.textContent = "Укажите имя";
      notify("error");
      return;
    }

    const payload = {
      items: items.map(i => ({ product_id: i.product_id, quantity: i.quantity })),
      full_name: fullName,
      phone: (data.get("phone") || "").toString().trim() || null,
      delivery_method: data.get("delivery_method"),
      delivery_address: (data.get("delivery_address") || "").toString().trim() || null,
      comment: (data.get("comment") || "").toString().trim() || null,
    };

    errorBox.textContent = "";
    showMainProgress();
    try {
      const order = await api.createOrder(payload);
      cart.clear();
      notify("success");
      location.hash = `#/success/${order.id}`;
    } catch (e) {
      errorBox.textContent = e.message;
      notify("error");
    } finally {
      hideMainProgress();
    }
  }

  setMainButton("Подтвердить заказ", submit);
  setBackButton(() => history.back());
}

// ─────────────────────────────────────────
// SUCCESS
// ─────────────────────────────────────────
export function viewSuccess(container, orderId) {
  hideMainButton();
  hideBackButton();
  notify("success");

  container.innerHTML = `
    <div class="success">
      <div class="success-icon">✅</div>
      <h1>Заказ принят</h1>
      <p>Номер заказа: <strong>#${escapeHtml(orderId)}</strong></p>
      <p class="hint">Менеджер свяжется с вами в Telegram в ближайшее время.</p>
      <button class="btn" id="back-to-shop">Вернуться в каталог</button>
    </div>
  `;
  container.querySelector("#back-to-shop").addEventListener("click", () => {
    location.hash = "#/catalog";
  });
}

// ─────────────────────────────────────────
// MY ORDERS
// ─────────────────────────────────────────
export async function viewOrders(container) {
  hideMainButton();
  hideBackButton();

  container.innerHTML = `<div class="loading">Загрузка…</div>`;

  let orders;
  try {
    orders = await api.myOrders();
  } catch (e) {
    container.innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
    return;
  }

  if (orders.length === 0) {
    container.innerHTML = `
      <div class="empty">
        <div class="empty-icon">📋</div>
        <h2>Заказов пока нет</h2>
        <p>Оформите первый заказ — он появится здесь.</p>
        <button class="btn" id="go-catalog">К каталогу</button>
      </div>
    `;
    container.querySelector("#go-catalog").addEventListener("click", () => {
      location.hash = "#/catalog";
    });
    return;
  }

  container.innerHTML = `
    <header class="header">
      <h1>📋 Мои заказы</h1>
    </header>

    <div class="orders-list">
      ${orders.map(orderRowHtml).join("")}
    </div>
  `;
}

function orderRowHtml(o) {
  const date = new Date(o.created_at).toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
  const statusLabel = STATUS_LABELS[o.status] || o.status;
  const deliveryLabel = DELIVERY_LABELS[o.delivery_method] || o.delivery_method;

  return `
    <div class="order-row">
      <div class="order-head">
        <span>Заказ #${o.id}</span>
        <span class="status status-${escapeHtml(o.status)}">${statusLabel}</span>
      </div>
      <div class="order-date">${escapeHtml(date)}</div>

      ${o.items.map(item => `
        <div class="order-item">
          ${item.product.main_photo ? `<img class="cart-thumb" src="${escapeHtml(item.product.main_photo)}" />` : `<div class="cart-thumb"></div>`}
          <div class="order-item-info">
            <div class="card-brand">${escapeHtml(item.product.brand)}</div>
            <div class="card-name">${escapeHtml(item.product.name)}</div>
            <div class="card-meta">${formatPrice(item.price_pln, item.price_usdt)}${item.quantity > 1 ? " × " + item.quantity : ""}</div>
          </div>
        </div>
      `).join("")}

      <div class="order-foot">
        <span class="card-meta">${deliveryLabel}</span>
        <strong>${formatPrice(o.total_pln, o.total_usdt)}</strong>
      </div>
    </div>
  `;
}
