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
          <svg viewBox="0 0 240 240" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M180 68L155 175c-1.7 7.5-6.3 9.4-12.7 5.8l-35-25.8-16.9 16.3c-1.9 1.9-3.4 3.4-7 3.4l2.5-35.4 64.5-58.3c2.8-2.5-.6-3.9-4.3-1.4l-79.7 50.2-34.3-10.7c-7.5-2.3-7.6-7.5 1.5-11.1l133.7-51.6c6.2-2.3 11.7 1.5 9.7 11.6z" fill="white"/>
          </svg>
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
