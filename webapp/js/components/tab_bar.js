// Manages the active state of the bottom tab bar and the favourites badge.

import { favorites } from "../state/favorites.js";

const ROUTES = ["#/catalog", "#/favorites", "#/about"];

function findOwningRoute(hash) {
  // Map sub-routes (e.g. #/product/42) to their owning tab.
  if (hash.startsWith("#/product")) return "#/catalog";
  if (hash.startsWith("#/custom-order")) return "#/about";  // sub-page reachable from About
  return ROUTES.includes(hash) ? hash : null;
}

export function initTabBar() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      location.hash = tab.dataset.route;
    });
  });

  // Favourites badge — update whenever the count changes.
  const badge = document.getElementById("favorites-badge");
  function renderBadge() {
    const n = favorites.count();
    if (!badge) return;
    if (n > 0) {
      badge.textContent = String(n);
      badge.classList.add("badge--visible");
    } else {
      badge.textContent = "";
      badge.classList.remove("badge--visible");
    }
  }
  renderBadge();
  favorites.subscribe(renderBadge);
}

export function setActiveTab(hash) {
  const owning = findOwningRoute(hash);
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("tab--active", tab.dataset.route === owning);
  });
}
