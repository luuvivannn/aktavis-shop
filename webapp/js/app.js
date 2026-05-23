import { cart } from "./cart.js";
import { initTelegram, tg } from "./tg.js";
import {
  viewCart,
  viewCatalog,
  viewCheckout,
  viewOrders,
  viewProduct,
  viewSuccess,
} from "./views.js";

initTelegram();

// Warn if launched without Telegram auth context (e.g., direct browser visit
// or ngrok interstitial broke the launch). Order submission won't work.
if (!tg?.initData) {
  const banner = document.createElement("div");
  banner.style.cssText =
    "background:#ff9500;color:white;padding:10px 14px;font-size:12px;" +
    "text-align:center;line-height:1.4;position:sticky;top:0;z-index:50;";
  banner.innerHTML =
    "⚠️ Откройте магазин через кнопку <b>«🛍 Открыть магазин»</b> в чате " +
    "с ботом, иначе оформление заказа не сработает.";
  document.body.insertBefore(banner, document.body.firstChild);
}

const app = document.getElementById("app");
const cartBadge = document.getElementById("cart-badge");

function updateCartBadge() {
  const count = cart.count();
  if (count > 0) {
    cartBadge.textContent = count;
    cartBadge.classList.add("visible");
  } else {
    cartBadge.textContent = "";
    cartBadge.classList.remove("visible");
  }
}

cart.onChange(updateCartBadge);
updateCartBadge();

function setActiveTab(route) {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.classList.toggle("active", tab.dataset.route === route);
  });
}

document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    location.hash = tab.dataset.route;
  });
});

async function route() {
  const hash = location.hash || "#/catalog";

  let m;
  if (!hash || hash === "#" || hash === "#/" || hash === "#/catalog") {
    setActiveTab("#/catalog");
    return viewCatalog(app);
  }
  if ((m = hash.match(/^#\/product\/(\d+)$/))) {
    setActiveTab(null);
    return viewProduct(app, m[1]);
  }
  if (hash === "#/cart") {
    setActiveTab("#/cart");
    return viewCart(app);
  }
  if (hash === "#/checkout") {
    setActiveTab(null);
    return viewCheckout(app);
  }
  if ((m = hash.match(/^#\/success\/(\d+)$/))) {
    setActiveTab(null);
    return viewSuccess(app, m[1]);
  }
  if (hash === "#/orders") {
    setActiveTab("#/orders");
    return viewOrders(app);
  }

  location.hash = "#/catalog";
}

window.addEventListener("hashchange", route);
route();
