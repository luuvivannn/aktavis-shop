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
      <h1>🎯 Индивидуальный заказ</h1>
    </header>

    <section class="info-section">
      <p>Мы принимаем персональные запросы и готовы оказать помощь
      в поиске интересующей вас позиции.</p>

      <p>Подбор изделий от ведущих мировых брендов осуществляется
      по стоимости, значительно более выгодной по сравнению с бутиками,
      с полным сопровождением сделки.</p>
    </section>

    <section class="info-section">
      <h2>🚚 Условия доставки</h2>
      <ul>
        <li>🇨🇳 Карго (Китай) — 20–30 дней — <b>10$ / кг</b></li>
        <li>✈️ Авиадоставка — 6–9 дней — <b>30$ / кг</b></li>
        <li>🇪🇺 Европа — 5–14 дней — <b>5$ / кг</b></li>
        <li>🇺🇸 США — сроки и стоимость индивидуально</li>
      </ul>
    </section>

    <section class="info-section warn">
      <p>Индивидуальные заказы принимаются <b>исключительно по 100% предоплате</b>.</p>
      <p>Рекомендуем заранее ознакомиться с отзывами,
      подтверждающими нашу репутацию.</p>
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
