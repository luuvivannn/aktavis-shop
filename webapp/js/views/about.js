// "О магазине" screen — static info content.
//
// Phase 4 stub: full layout, basic content. We can polish copy in a
// later phase if needed.

import { hideBackButton, hideMainButton } from "../tg.js";

export function viewAbout(container) {
  hideMainButton();
  hideBackButton();

  container.innerHTML = `
    <header class="header">
      <div class="brand-header">
        <div class="brand-logo">
          <img src="img/brand_logo.jpg" alt="AKTAVIS" />
        </div>
        <h1>AKTAVIS.EU</h1>
      </div>
      <p class="hint">Оригинальные вещи · Самая быстрая доставка в любую точку мира</p>
    </header>

    <section class="info-section">
      <h2>🤍 Принципы работы</h2>
      <ul>
        <li>Все товары — 100% оригинал</li>
        <li>Продажи окончательные, обмен и возврат не предусмотрены</li>
        <li>Бронирование — только по задатку</li>
        <li>Доп. фото и видео — по запросу</li>
        <li>Приоритет оперативным покупателям</li>
        <li>Примерки возможны в Варшаве</li>
      </ul>
    </section>

    <section class="info-section">
      <h2>📦 Доставка</h2>
      <ul>
        <li>🚚 Курьер по Варшаве</li>
        <li>✈️ Европа и весь мир — транспортной компанией по выбору клиента</li>
      </ul>
    </section>

    <section class="info-section">
      <h2>✉️ Связь</h2>
      <ul class="contact-list">
        <li><a href="https://t.me/+cUh6oXRMk3Q4YWNi" target="_blank">Telegram канал</a></li>
        <li><a href="https://t.me/actavis_feedback" target="_blank">Отзывы</a></li>
        <li><a href="https://www.instagram.com/aktavis.eu/" target="_blank">Instagram</a></li>
      </ul>
    </section>

    <section class="info-section">
      <a href="#/custom-order" class="link-card">
        <div class="link-card-title">🎯 Индивидуальный заказ</div>
        <div class="link-card-hint">Не нашли нужное? Закажем под вас.</div>
      </a>
    </section>
  `;
}
