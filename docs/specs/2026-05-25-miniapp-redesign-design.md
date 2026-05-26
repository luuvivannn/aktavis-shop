# Mini App Redesign — Design Document

**Date:** 2026-05-25
**Project:** AKTAVIS.EU Telegram Shop
**Status:** Pending user review

## Overview

The Mini App is pivoting from "e-commerce with cart/checkout" to a
"showcase catalog with direct seller contact". Sales move out of the app
and back into DMs with the seller. The app's job becomes: browse a clean
catalog, save favourites, and one-tap contact the seller with the
right item context.

Alongside the UX redesign, the project moves toward "Mini App first":
channel posts get an inline button that opens the Mini App on the exact
product (Direct Link Mini App with `start_param` deep-linking).

## Goals

1. Replace brand-based filtering with type-based categories.
2. Add a NEW badge for the 3 most recently published items per category.
3. Add per-category filters (price, size) and sorts (price, recency).
4. Add a Favourites tab persisted in `localStorage`.
5. Replace cart/checkout with a single "Написать продавцу" button that
   deep-links to `t.me/aktavis_eu` with a pre-filled message.
6. Strip out all order-related code (Mini App, API, bot).
7. Register the Mini App as a Direct Link Mini App and auto-attach an
   inline button to channel posts pointing to the specific product.

## Non-goals

- Real-time order processing through the app (intentionally removed).
- Inventory/stock management in the app (still via bot/channel hashtags).
- Multi-language support (Russian only, like today).
- Push notifications to clients beyond `start_param` deep-links.

## Architecture Overview

```
┌──────────────────────────┐         ┌────────────────────────┐
│   Telegram Channel       │   post  │  Bot (Railway)         │
│   @aktavis_eu           ├────────►│  parses + asks admin   │
└──────────────────────────┘         └───────┬────────────────┘
        ▲                                    │ admin clicks
        │ edit message,                      │ "✅ Опубликовать"
        │ add inline button                  ▼
        │                            ┌────────────────────────┐
        └────────────────────────────┤  Product saved IN_STOCK│
                                     │  Bot edits channel post│
                                     │  to add inline button  │
                                     │  → t.me/bot/shop?p=N   │
                                     └───────┬────────────────┘
                                             │ client taps button
                                             ▼
                                     ┌────────────────────────┐
                                     │  Mini App opens with   │
                                     │  start_param=p_42      │
                                     │  → product 42 detail   │
                                     └───────┬────────────────┘
                                             │ taps "Написать продавцу"
                                             ▼
                                     ┌────────────────────────┐
                                     │  t.me/aktavis_eu       │
                                     │  with pre-filled msg   │
                                     └────────────────────────┘
```

## Backend Changes

### Schema: `ProductCategory` enum

Current values: `CLOTHING`, `SHOES`, `ACCESSORIES`, `BAGS`, `OTHER`.

New values:
- `BAGS` — "Сумки"
- `SHOES` — "Обувь"
- `TOPS` — "Кофты / Футболки"
- `JACKETS` — "Куртки"
- `PANTS` — "Штаны" (added during Phase 1 — inventory had pants we needed to surface)
- `ACCESSORIES` — "Аксессуары"
- `CUSTOM_ORDER` — "Под заказ" (special: no real products, info-only page)
- `OTHER` — fallback

`CLOTHING` is **removed**. Existing rows must be migrated.

### Migration: existing 34 `clothing` products

Auto-classification rules (case-insensitive keyword match against
`Product.name`):

| Keywords | New category |
|---|---|
| худи, кофта, свитшот, лонгслив, футболка, майка, поло | TOPS |
| куртка, ветровка, пуховик, пальто, плащ, жилетка, пиджак, бомбер | JACKETS |
| (no match) | OTHER (flagged for review) |

After auto-classification, the migration prints a table of all
re-categorised products. Admin (user) reviews and provides corrections
via a small follow-up SQL/admin script. Decisions cached so re-runs
don't re-classify already-touched rows.

### Parser update

`bot/channel_parser.py` `CATEGORY_KEYWORDS` updated to match new enum.
Same keyword list as the migration.

### Code removal

Files / code to **delete entirely**:
- `bot/handlers/orders.py`
- `bot/handlers/admin.py` (order management callbacks + `/orders_all` +
  `/stats`)
- `api/routers/orders.py`
- `database/repositories.py` → `OrderRepository` class
- `bot/notifications.py` → `notify_admins_new_order`,
  `notify_client_status_change`, `format_order_for_admin`,
  `CLIENT_STATUS_MESSAGES`, `STATUS_LABELS` (those used only by orders)
- `bot/callbacks.py` → `OrderAction` (keep `ChannelPostAction`)
- Webapp views/state: `cart.js`, cart-related code in `views.js`
- `Order`, `OrderItem` SQLAlchemy models — keep tables for one
  transitional deploy, then drop in a follow-up
- ADMIN_COMMANDS in `bot/commands.py` becomes empty (just shows user
  commands to admin)

### API changes

Endpoints to remove:
- `POST /api/orders`
- `GET /api/orders/my`
- `GET /api/orders/{id}`
- `GET /api/me`

New / changed endpoints:
- `GET /api/products` — adds `sort_by` (`price_asc`, `price_desc`,
  `created_desc`) and `size` filter (substring match). `category` filter
  uses new enum values. Drops `brand` filter.
- `GET /api/products/{id}` — adds `is_new: bool` field
- `GET /api/products/brands` — **removed** (no brand filter anymore)
- `GET /api/products/search` — kept (search by name/brand/description)

### NEW badge logic (server-side)

`is_new` is computed at query time, not stored:

```
For each category, the top 3 products ordered by
  (created_at DESC, id DESC)
where status == IN_STOCK
get is_new = True.
```

Implementation: when serializing products for the list endpoint, run a
single query per visible category to get the top-3 IDs, then mark those
IDs in the response. Alternative: a precomputed window function in
SQLite. Picking the simple two-query approach for clarity.

## Mini App Frontend

### File structure

```
webapp/
├── index.html
├── css/
│   └── style.css
└── js/
    ├── app.js               # bootstrap + router
    ├── api.js               # API client (no orders methods)
    ├── tg.js                # Telegram WebApp helpers (unchanged)
    ├── state/
    │   ├── favorites.js     # localStorage favourites
    │   └── filters.js       # active filters/sort per category
    ├── views/
    │   ├── catalog.js
    │   ├── product.js
    │   ├── favorites.js
    │   ├── about.js
    │   └── custom_order.js
    └── components/
        ├── category_pills.js
        ├── product_card.js
        ├── filter_sheet.js
        └── tab_bar.js
```

Old files (`cart.js`, large `views.js`) are deleted; `views.js` content
splits into per-screen files in `webapp/js/views/`.

### Routing

Hash-based, same as today:

| Hash | View | Notes |
|---|---|---|
| `#/catalog` (default) | catalog | with optional `?cat=X&size=Y&sort=Z` |
| `#/product/{id}` | product detail | |
| `#/favorites` | favorites | |
| `#/about` | about | |
| `#/custom-order` | custom order info | |

Deep link from channel: `t.me/bot/shop?startapp=p_42` → app reads
`start_param`, on boot routes to `#/product/42`.

### State

- **Favorites** (`state/favorites.js`): array of product IDs in
  `localStorage` under key `aktavis_fav_v1`. Pub/sub for UI updates.
- **Filters** (`state/filters.js`): per-category active filters
  (`size`, `price_min`, `price_max`, `sort_by`) cached in memory
  (resets on app close, intentional).

### Screens

#### Catalog (`views/catalog.js`)

Layout (top → bottom):
1. Header: shop name + small subtitle
2. `category-pills` component (horizontal scroll): Все, Сумки, Обувь,
   Кофты/Футболки, Куртки, Штаны, Аксессуары, Под заказ
3. Filter/Sort row: button "Фильтры" opens bottom sheet (`filter_sheet`)
4. Product grid (2 columns) of `product-card` components

Special category "Под заказ" doesn't show grid — instead shows the
custom-order info screen content inline (or routes to it).

#### Product detail (`views/product.js`)

Same overall layout as today (gallery + description), with these changes:
- Top-right of header: heart icon for favourite toggle
- NEW badge top-left of gallery if `is_new`
- MainButton: "Написать продавцу"
  - On click: `Telegram.WebApp.openTelegramLink(deepLink)`
  - Pre-filled message body includes the **product photo URL** so the
    seller sees the item immediately as a preview in Telegram:
    ```
    Привет! Хочу купить {brand} {name}, размер {size}
    {photo_url}
    ```
  - `photo_url` = absolute URL of the first product photo, e.g.
    `https://web-production-bcfd3.up.railway.app/photos/channel_42_0.jpg`
  - Deep link:
    ```js
    const text =
      `Привет! Хочу купить ${brand} ${name}, размер ${size}\n${photoUrl}`;
    const url = `https://t.me/aktavis_eu?text=${encodeURIComponent(text)}`;
    ```
  - Telegram auto-renders the trailing URL as an image preview in the
    input box; once the user sends it, the seller's chat shows the
    photo above the text.
- No cart logic

#### Favorites (`views/favorites.js`)

- Reads IDs from `state/favorites.js`
- Fetches product data for those IDs (batch endpoint OR sequential
  fetches — sequential is fine for typical list size)
- Grid of `product-card` components, same look as catalog
- Empty state: icon + "В избранном пусто" + button "Открыть каталог"
- Removing a favourite (heart click) updates the list immediately

#### About (`views/about.js`)

Static content, ported from the bot's `/about` text:
- Принципы работы
- Контакты: @actavis_eu, t.me/actavis_feedback, instagram
- Локация: Warszawa, Ursynów
- Условия доставки (curбurier, Europe, worldwide)

#### Custom order (`views/custom_order.js`)

Static content from user's brief, plus optional delivery rates from
original channel post:
- Текст услуги (от пользователя)
- Carriers/timing: 🇨🇳 Карго 10$/кг, ✈️ Авиа 30$/кг, 🇪🇺 Европа 5$/кг,
  🇺🇸 США индивидуально
- Big button "Написать продавцу" → `t.me/aktavis_eu?text=Привет, хочу заказать индивидуально...`

### Components

#### `category-pills`

Horizontal scroll, pill buttons. Active state visual = filled bg /
inverted colour. Click → updates active filter + re-renders grid.

#### `product-card`

| Slot | Content |
|---|---|
| Top-left | `NEW` badge (only if `is_new`) |
| Top-right | Heart icon (filled if in favorites) |
| Center | Product photo (1:1 aspect ratio) |
| Bottom | Brand · name · price |

Tap on card body → product detail. Tap on heart → toggle favourite
(does not navigate).

#### `filter-sheet`

Telegram's `Telegram.WebApp.showPopup` is too restrictive — custom
bottom sheet. Contains:
- Sort: "По новизне" / "Цена ↑" / "Цена ↓"
- Size: pills for category-relevant sizes
  - For SHOES: 36–46 (+ half sizes if found in catalog)
  - For TOPS/JACKETS/PANTS: XS/S/M/L/XL/XXL
  - Hidden for BAGS/ACCESSORIES/CUSTOM_ORDER
- Price range: two-handle slider OR two number inputs
- "Применить" button at bottom, "Сбросить" link

#### `tab-bar`

Three tabs at bottom (sticky):
| Icon | Label | Route |
|---|---|---|
| 🛍 | Каталог | `#/catalog` |
| ❤ | Избранное | `#/favorites` |
| ℹ️ | О магазине | `#/about` |

## Deep Link Integration

### Direct Link Mini App registration

User task: in `@BotFather`:
1. `/mybots` → `@aktaviuseu_bot` → Bot Settings → Configure Mini App
2. New Mini App: name `shop`
3. URL: `https://web-production-bcfd3.up.railway.app/webapp/`
4. Photo: shop logo (optional, can do later)

Result: public URL `t.me/aktaviuseu_bot/shop`.

### Start param handling

In `app.js`, on boot:

```js
const startParam = window.Telegram?.WebApp?.initDataUnsafe?.start_param;
if (startParam && startParam.startsWith("p_")) {
    const productId = startParam.slice(2);
    location.hash = `#/product/${productId}`;
}
```

Format: `p_<id>` for "open product with id". Future-proof for `c_<cat>`
etc.

### Auto-attach inline button to channel posts

When admin clicks "✅ Опубликовать" on a channel-post preview:

1. Product gets ID (already happens today, status → IN_STOCK)
2. Bot constructs deep link:
   `https://t.me/aktaviuseu_bot/shop?startapp=p_<id>`
3. Bot constructs inline keyboard with one button:
   `[ 🛍 Открыть в магазине ]` → deep link
4. Bot calls `bot.edit_message_reply_markup(
       chat_id=product.channel_chat_id,
       message_id=product.channel_message_id,
       reply_markup=keyboard)`

Error handling: if edit fails (message too old, perms revoked), log
warning, continue. Don't fail the publish action.

### Bulk back-fill (optional, post-MVP)

Admin command `/backfill_buttons` iterates existing IN_STOCK products
with `channel_message_id` set, edits their posts to add the button.
Rate-limited (1/sec) to avoid Telegram limits.

## Bot Changes Summary

Files modified:
- `bot/handlers/channel.py` — add button attachment after publish
- `bot/commands.py` — remove `/orders_all`, `/stats`, `/admin` from
  ADMIN_COMMANDS; admin sees same commands as user
- `bot/handlers/__init__.py` — drop registrations of removed routers
- `bot/notifications.py` — remove order-related functions

Files removed entirely:
- `bot/handlers/orders.py`
- `bot/handlers/admin.py`

The bot still:
- Receives channel posts and sends admin previews
- Handles `/start`, `/about`, `/delivery`, `/contact`
- Updates channel posts with inline buttons after admin publishes

## Migration Order

1. **Branch + spec freeze** — branch `redesign-v2` cut from `main`
2. **Backend schema**: extend `ProductCategory` enum, run migration to
   reclassify 34 products. **Don't drop old `CLOTHING` value yet** — for
   safety, keep both enums working until step 7.
3. **Parser update**: new `CATEGORY_KEYWORDS`
4. **API changes**: new filters/sorts, drop order endpoints
5. **Bot cleanup**: remove order handlers, update commands
6. **Mini App rewrite**: per the structure above
7. **Deep-link integration**: Direct Link registration + auto-attach
   button + start_param routing
8. **Drop `CLOTHING` enum value** after data verified
9. **Drop `Order`, `OrderItem` tables** in a follow-up clean-up commit

Each step deployable independently; rollback at any step doesn't break
the live shop.

## Testing Checklist

- [ ] All 73 existing products visible in catalog
- [ ] Each clothing item lands in correct new category
- [ ] Brand filter completely gone; category pills work
- [ ] NEW badge on top 3 newest in_stock per category
- [ ] Sorting by price asc/desc works
- [ ] Sorting by recency works (newest first)
- [ ] Size filter shows correct values per category
- [ ] Size filter substring match correct ("M" matches "M (факт M-L)")
- [ ] Price range filter works
- [ ] Heart toggles work, persist in localStorage
- [ ] Favorites tab shows correct items
- [ ] Empty favorites tab shows correct state
- [ ] About tab shows full content
- [ ] Custom order tab shows full content + delivery rates
- [ ] Tap product → detail screen works
- [ ] Detail screen heart works
- [ ] "Написать продавцу" opens t.me/aktavis_eu with correct pre-fill
- [ ] Pre-filled message includes the product photo URL on a new line
- [ ] Telegram renders that URL as a photo preview in the input box
- [ ] BotFather Mini App configured, `t.me/bot/shop` opens app
- [ ] `start_param=p_42` routes to product 42
- [ ] After admin publishes, channel post gets inline button
- [ ] Tapping inline button opens product detail directly
- [ ] No order endpoints respond (404)
- [ ] No order commands respond in bot
- [ ] Existing test orders (#1, #2, #3) cleaned up

## Open Questions (for user)

None blocking. Optional:
- Logo for BotFather Mini App registration?
- Should "Под заказ" delivery rates use exact numbers from old channel
  post (10/30/5 $/kg) or fresh values?

## Out-of-scope (future)

- Server-side favorites sync across devices
- Multi-photo upload via admin command
- "Также покупают" recommendations
- Coupon/promo codes
- Telegram Stars / native checkout

---

End of design document.
