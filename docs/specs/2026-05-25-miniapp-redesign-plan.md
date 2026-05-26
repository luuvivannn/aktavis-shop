# Mini App Redesign — Implementation Plan

**Date:** 2026-05-25
**Companion to:** `2026-05-25-miniapp-redesign-design.md`
**Status:** Ready for execution

## Strategy

Seven phases, each independently deployable and testable. After every
phase the shop remains live and working. We can pause at any point
without leaving the codebase in a broken state.

Local testing precedes every `git push`. We don't reload Railway with
half-broken changes.

## Branches and Commits

Working directly on `main` (current workflow). Each phase gets one or
two atomic commits with clear messages so we can revert a single phase
if needed.

If at any point we want to be safer, we can branch (`redesign-v2`) and
merge back when stable — but for this size of project, direct-to-main
with small commits is fine.

---

## Phase 1 — Backend: Categories & migration

**Goal:** new category taxonomy in place, existing 34 clothing items
reclassified correctly.

### Changes

| File | Action |
|---|---|
| `database/models.py` | Add `TOPS`, `JACKETS`, `CUSTOM_ORDER` to `ProductCategory`. **Keep `CLOTHING`** for one phase to allow rollback. |
| `bot/channel_parser.py` | Update `CATEGORY_KEYWORDS` to map new categories. |
| `scripts/migrate_categories.py` | New: reads existing CLOTHING products, reclassifies based on name keywords, prints results, updates DB. |
| `database/db.py` | Update SEED_PRODUCTS to use new categories (Худи → TOPS, Ветровка → JACKETS, etc.) |

### Migration script logic

```
1. SELECT all products WHERE category = 'clothing'
2. For each: inspect product.name keyword-by-keyword
3. Classify into TOPS / JACKETS / OTHER (fallback)
4. Print summary table: id | brand | name | old_cat → new_cat
5. Prompt "Apply? (y/n)"
6. If yes: UPDATE per row, commit, log results
```

### Testing

- Run locally against local `shop.db` first
- Verify all 34 items got classified
- Eyeball the new categories; if anything looks wrong, abort and fix
  keyword list before applying to prod

### Deploy

```powershell
git commit -m "Phase 1: new categories + migration script"
git push
# Railway auto-deploys
# Then run migration on Railway via:
railway run python scripts/migrate_categories.py
# (Or via a temporary admin endpoint — TBD when we get there.)
```

### Rollback

If migration goes sideways: `UPDATE products SET category='clothing'
WHERE category IN ('tops','jackets')`. Old enum still exists.

### Acceptance

- [ ] All 73 products have valid categories
- [ ] No products with category 'clothing' (or only those we couldn't classify)
- [ ] Bot's channel parser produces new categories for new posts

---

## Phase 2 — Backend: API for new catalog

**Goal:** the products API supports filters and sorts the new Mini App
needs; orders API gone.

### Changes

| File | Action |
|---|---|
| `api/schemas.py` | Add `is_new: bool` to `ProductSummary` / `ProductDetail`. Add filter/sort enums for query params. |
| `api/routers/products.py` | Accept `category`, `size`, `sort_by`, `price_min`, `price_max` query params. Compute `is_new` per category (top-3 most recent IN_STOCK). |
| `api/routers/products.py` | Remove `/api/products/brands` endpoint (no brand filter anymore). |
| `api/routers/orders.py` | **Delete file** |
| `api/app.py` | Drop `orders` router registration. |
| `api/dependencies.py` | Drop `current_telegram_user` dep (no longer needed for orders). Keep `db_session`. |

### `is_new` computation

```python
async def _compute_is_new_ids(session) -> set[int]:
    """For each category, return ids of top-3 most recent IN_STOCK products."""
    new_ids = set()
    for cat in ProductCategory:
        if cat == ProductCategory.CUSTOM_ORDER:
            continue
        stmt = (
            select(Product.id)
            .where(Product.category == cat, Product.status == ProductStatus.IN_STOCK)
            .order_by(Product.created_at.desc(), Product.id.desc())
            .limit(3)
        )
        ids = (await session.scalars(stmt)).all()
        new_ids.update(ids)
    return new_ids
```

Called once per list-endpoint request; results merged into the response.

### Size filter logic

```python
if size:
    stmt = stmt.where(Product.size.ilike(f"%{size}%"))
```

Simple substring match (covers "M", "XS (факт M-L)", "5 (L-XL)", "42",
"6.5 LV (41.5-42.5)").

### Testing

- `curl https://web-.../api/products?category=shoes&size=42`
- `curl https://web-.../api/products?sort_by=price_asc`
- Verify `is_new` is set on expected products

### Deploy

```powershell
git commit -m "Phase 2: new product filters/sorts + drop order endpoints"
git push
```

### Acceptance

- [ ] `/api/products` accepts all new params
- [ ] `is_new` correctly shows top 3 per category
- [ ] `/api/orders/*` returns 404
- [ ] `/api/products/brands` returns 404
- [ ] Existing live Mini App still works (because we haven't changed the
      old API contract for the fields it uses)

---

## Phase 3 — Bot cleanup

**Goal:** all order-related bot code gone; only catalog/channel commands
remain.

### Changes

| File | Action |
|---|---|
| `bot/handlers/orders.py` | **Delete** |
| `bot/handlers/admin.py` | **Delete** (had order-status callbacks + `/orders_all` + `/stats` + `/admin`) |
| `bot/callbacks.py` | Remove `OrderAction`; keep `ChannelPostAction` |
| `bot/notifications.py` | Remove `notify_admins_new_order`, `notify_client_status_change`, `format_order_for_admin`, status maps |
| `bot/commands.py` | Reduce `ADMIN_COMMANDS` to match `USER_COMMANDS`. `ensure_admin_commands()` becomes redundant but harmless. |
| `bot/handlers/__init__.py` | Drop `orders` and `admin` router registrations |
| `bot/keyboards.py` | Remove `order_admin_keyboard` |

### Testing

- `/orders_all` in bot → no response (or bot complains about unknown command)
- `/stats` in bot → no response
- `/admin` in bot → no response
- `/start` works
- Channel post triggers admin preview as before
- "✅ Опубликовать" still works

### Deploy

```powershell
git commit -m "Phase 3: remove all order-related bot code"
git push
```

### Acceptance

- [ ] Removed commands don't show in bot UI
- [ ] No errors in Railway logs on startup
- [ ] Channel sync still works end-to-end (preview → publish)

---

## Phase 4 — Mini App: refactor structure (no UI changes yet)

**Goal:** code is split into modules per the design. **No new features
yet.** All existing functionality keeps working — just better organised.

### Changes

| Old file | New location |
|---|---|
| `webapp/js/views.js` (one big file) | split into: |
| → catalog view | `webapp/js/views/catalog.js` |
| → product view | `webapp/js/views/product.js` |
| → cart view (will be deleted later) | `webapp/js/views/cart.js` |
| → checkout view (will be deleted later) | `webapp/js/views/checkout.js` |
| → success view (will be deleted later) | `webapp/js/views/success.js` |
| → orders view (will be deleted later) | `webapp/js/views/orders.js` |
| `webapp/js/cart.js` | `webapp/js/state/cart.js` (temp, deleted in Phase 5) |
| (new) | `webapp/js/state/favorites.js` (skeleton) |
| (new) | `webapp/js/state/filters.js` (skeleton) |
| `webapp/js/app.js` | updated imports, routing still includes old routes |

Phase 4 is **structural only**. Nothing visible changes. We verify the
old Mini App still works in production after the refactor.

### Testing

- Open Mini App → catalog loads
- Add to cart → cart shows item
- Checkout flow (won't be tested in prod because we'll remove it next,
  but should still work)

### Deploy

```powershell
git commit -m "Phase 4: refactor Mini App into modules (no UX changes)"
git push
```

### Acceptance

- [ ] Old Mini App fully functional
- [ ] No regressions
- [ ] Files clearly split, each under ~200 lines

---

## Phase 5 — Mini App: new screens & behaviour

**Goal:** the new UX is live. Old cart/checkout/orders gone from Mini
App. Three tabs at bottom (Catalog / Favorites / About).

### Changes

| Old | New |
|---|---|
| `webapp/js/views/cart.js` | **Delete** |
| `webapp/js/views/checkout.js` | **Delete** |
| `webapp/js/views/success.js` | **Delete** |
| `webapp/js/views/orders.js` | **Delete** |
| `webapp/js/state/cart.js` | **Delete** |
| `webapp/js/api.js` | drop order methods |
| `webapp/js/views/catalog.js` | rewrite: category pills + filter sheet + product grid |
| `webapp/js/views/product.js` | rewrite: heart, "Написать продавцу" with photo URL |
| `webapp/js/views/favorites.js` | new |
| `webapp/js/views/about.js` | new |
| `webapp/js/views/custom_order.js` | new |
| `webapp/js/components/category_pills.js` | new |
| `webapp/js/components/product_card.js` | new |
| `webapp/js/components/filter_sheet.js` | new |
| `webapp/js/components/tab_bar.js` | rewrite (3 tabs: catalog/favorites/about) |
| `webapp/js/state/favorites.js` | full impl with localStorage |
| `webapp/js/state/filters.js` | full impl (in-memory) |
| `webapp/js/app.js` | new routes; remove cart/checkout/orders |
| `webapp/index.html` | update tab bar markup if needed |
| `webapp/css/style.css` | styles for new components (category pills, filter sheet, heart icon, NEW badge) |

### Pre-filled "Написать продавцу" message

```js
function buildSellerLink(product) {
  const photoUrl = product.main_photo
    ? new URL(product.main_photo, window.location.origin).href
    : "";
  const size = product.size || "—";
  const lines = [
    `Привет! Хочу купить ${product.brand} ${product.name}, размер ${size}`,
  ];
  if (photoUrl) lines.push(photoUrl);
  const text = lines.join("\n");
  return `https://t.me/aktavis_eu?text=${encodeURIComponent(text)}`;
}
```

On click: `Telegram.WebApp.openTelegramLink(buildSellerLink(product))`.

### Testing checklist (local)

- Catalog grid: 2 cols, NEW badge on right items
- Tap category pill → grid filters
- "Фильтры" button → sheet opens
- Apply size + price filter → grid updates
- Sort by price → order changes
- Tap card → product detail
- Heart on card or detail toggles favorite (persists after reload)
- Favorites tab shows hearted items
- Empty favorites shows empty state
- About tab shows full content
- Custom Order tab shows full content
- "Написать продавцу" opens t.me/aktavis_eu with photo URL on new line
- Telegram renders photo preview in input

### Deploy

```powershell
git commit -m "Phase 5: new Mini App UX (catalog filters, favorites, seller contact)"
git push
```

### Acceptance

- [ ] All testing checklist items pass on real Telegram clients
- [ ] No 404s in network tab
- [ ] No console errors

---

## Phase 6 — Deep Link Mini App

**Goal:** Mini App is registered as Direct Link in BotFather; channel
posts auto-get an inline button after admin publishes.

### User tasks (BotFather, ~3 min)

1. Open `@BotFather` → `/mybots` → `@aktaviuseu_bot`
2. **Bot Settings** → **Configure Mini App** → **Add Mini App**
3. Short name: `shop`
4. URL: `https://web-production-bcfd3.up.railway.app/webapp/`
5. (Optional) Photo: shop logo
6. Resulting link: `https://t.me/aktaviuseu_bot/shop`

### Code changes

| File | Action |
|---|---|
| `webapp/js/app.js` | On boot, read `Telegram.WebApp.initDataUnsafe.start_param`. If matches `p_<id>`, route to `#/product/<id>`. |
| `bot/handlers/channel.py` | In the publish-callback handler, after setting status to IN_STOCK, call `bot.edit_message_reply_markup` on the original channel post to attach an inline keyboard button. |
| `config.py` | Add `MINIAPP_DEEPLINK_BASE` env var, default `https://t.me/aktaviuseu_bot/shop`. |

### Inline keyboard attachment

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import MINIAPP_DEEPLINK_BASE

async def attach_shop_button(bot, product):
    if not (product.channel_chat_id and product.channel_message_id):
        return
    url = f"{MINIAPP_DEEPLINK_BASE}?startapp=p_{product.id}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🛍 Открыть в магазине", url=url),
    ]])
    try:
        await bot.edit_message_reply_markup(
            chat_id=product.channel_chat_id,
            message_id=product.channel_message_id,
            reply_markup=keyboard,
        )
    except TelegramBadRequest as exc:
        logger.warning("Could not attach button to channel post %s: %s",
                       product.channel_message_id, exc)
```

### Testing

- Register Mini App in BotFather
- Add env var on Railway (`MINIAPP_DEEPLINK_BASE`)
- Push code
- Have channel admin post a new test product
- Approve via preview
- Check the channel post — should now have inline button
- Tap button — Mini App opens at the product detail
- Use "Написать продавцу" — link with photo URL works

### Deploy

```powershell
git commit -m "Phase 6: Direct Link Mini App + auto channel-post buttons"
git push
```

### Acceptance

- [ ] BotFather Mini App configured
- [ ] `t.me/aktaviuseu_bot/shop` opens Mini App
- [ ] `?startapp=p_42` opens product 42 directly
- [ ] New channel posts get button after publish
- [ ] Button click works on iOS, Android, Desktop

---

## Phase 7 — Final cleanup

**Goal:** drop all dead code and tables. Project is lean.

### Changes

| File | Action |
|---|---|
| `database/models.py` | Remove `Order`, `OrderItem` classes. Remove `OrderStatus`, `DeliveryMethod` enums. Remove `CLOTHING` from `ProductCategory`. |
| `database/repositories.py` | Remove `OrderRepository`, `CartItem`, `ProductNotAvailableError`, `ProductNotFoundError` if only used by orders. |
| `database/__init__.py` | Drop removed exports. |
| Migration: drop tables `orders` and `order_items` | One-time SQL via Railway shell or temporary endpoint |
| `database/db.py` | Drop `Migration applied: ALTER TABLE products...` lines that reference removed enum values (`CLOTHING`). |

### Testing

- Bot starts cleanly, no errors in logs
- Catalog still works (no regressions from removed code)
- DB inspection shows no `orders` / `order_items` tables

### Deploy

```powershell
git commit -m "Phase 7: drop dead code (orders, CLOTHING enum, unused models)"
git push
```

### Acceptance

- [ ] `bot/` and `api/` import cleanly without warnings
- [ ] No references to `Order` / `OrderItem` remain (`git grep` confirms)
- [ ] DB has only `products` table

---

## Timing Estimate

| Phase | Estimated time |
|---|---|
| 1 — Categories + migration | 2-3 h |
| 2 — API filters/sorts | 2-3 h |
| 3 — Bot cleanup | 1 h |
| 4 — Mini App refactor (no UX changes) | 2-3 h |
| 5 — New Mini App UX | 6-8 h |
| 6 — Deep Link | 2-3 h |
| 7 — Final cleanup | 1 h |
| **Total** | **~16-22 h** |

Realistic calendar: 2-3 active sessions over 2-3 days, allowing time for
your review at each phase.

## Communication checkpoints

After each phase I'll:
1. Push the commit
2. Tell you: "Phase N deployed — please test [specific scenarios]"
3. Wait for your "ок" or feedback before proceeding to next phase

This keeps you in control and prevents long uninterrupted code blasts.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Migration mis-classifies an item | Manual review step before commit |
| Deep-link button edit fails on old posts | Warn but don't fail; only required for new posts |
| Removing orders breaks `/orders_all` mid-deploy | Phase 3 (bot) deploys before Phase 5 (Mini App), so no user-facing break |
| Style differences across Telegram clients | Use Telegram theme variables + test on iOS+Android+Desktop |
| Telethon session bricks | Not relevant for this redesign |

## What I need from you to start

Just confirm:
- ☑ Plan looks good
- ☑ Starting with **Phase 1** (categories + migration)

I'll then start implementing Phase 1, push it, ask you to test, and we
move forward step by step.

---

End of implementation plan.
