// SPA entry point.
//
// Routes (hash-based):
//   #/catalog            catalog grid (default)
//   #/product/{id}       product detail
//   #/favorites          favourites list
//   #/about              shop info
//   #/custom-order       custom-order info page
//
// Direct-link support:
//   When Telegram opens the Mini App as a Direct Link with a
//   ``startapp`` parameter (e.g. from a channel post), the value lands
//   in ``initDataUnsafe.start_param``. We parse it and translate
//   ``p_42`` into a product-detail route on boot.

import { initTabBar, setActiveTab } from "./components/tab_bar.js";
import { initTelegram, tg } from "./tg.js";
import { viewAbout } from "./views/about.js";
import { viewCatalog } from "./views/catalog.js";
import { viewCustomOrder } from "./views/custom_order.js";
import { viewFavorites } from "./views/favorites.js";
import { viewProduct } from "./views/product.js";

initTelegram();
initTabBar();

const app = document.getElementById("app");

// Apply start_param BEFORE the first route() call so a deep link goes
// straight to the right screen with no flash of the default catalog.
applyStartParam();

async function route() {
  const hash = location.hash || "#/catalog";
  setActiveTab(hash);

  let m;
  if (!hash || hash === "#" || hash === "#/" || hash === "#/catalog") {
    return viewCatalog(app);
  }
  if ((m = hash.match(/^#\/product\/(\d+)$/))) {
    return viewProduct(app, m[1]);
  }
  if (hash === "#/favorites") {
    return viewFavorites(app);
  }
  if (hash === "#/about") {
    return viewAbout(app);
  }
  if (hash === "#/custom-order") {
    return viewCustomOrder(app);
  }

  // Unknown route — fall back to catalog.
  location.hash = "#/catalog";
}

function applyStartParam() {
  const param = tg?.initDataUnsafe?.start_param;
  if (!param) return;

  let m;
  if ((m = param.match(/^p_(\d+)$/))) {
    location.hash = `#/product/${m[1]}`;
    return;
  }
  if (param === "favorites") {
    location.hash = "#/favorites";
    return;
  }
  if (param === "about") {
    location.hash = "#/about";
    return;
  }
  if (param === "custom_order" || param === "custom-order") {
    location.hash = "#/custom-order";
  }
}

window.addEventListener("hashchange", route);
route();
