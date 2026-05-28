// "Под заказ" / Custom order screen — info page with a single
// "Написать продавцу" button.

import { haptic, setBackButton, setMainButton, tg } from "../tg.js";

const SELLER_USERNAME = "aktavis_eu";

function buildCustomOrderLink() {
  const text = "Привет! Хочу обсудить индивидуальный заказ.";
  return `https://t.me/${SELLER_USERNAME}?text=${encodeURIComponent(text)}`;
}

export function viewCustomOrder(container) {
  container.innerHTML = `
    <header class="header">
      <h1>🎯 Под заказ</h1>
    </header>

    <section class="info-section">
      <img src="img/custom_order_banner.jpg" alt="Под заказ" />
    </section>

    <section class="info-section">
      <p><b>Привезу вещь любой сложности в самые кратчайшие сроки ‼️</b></p>
      <p><b>Намного ниже рынка!!!</b></p>
    </section>
  `;

  const link = buildCustomOrderLink();
  setMainButton("Написать продавцу", () => {
    haptic("medium");
    if (tg?.openTelegramLink) {
      tg.openTelegramLink(link);
    } else {
      window.open(link, "_blank");
    }
  });

  setBackButton(() => history.back());
}
