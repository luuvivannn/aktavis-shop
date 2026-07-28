"""Parser for Telegram channel posts in the AKTAVIS.EU format.

Expected post layout (Russian):

    Louis Vuitton Outdoor
    Размер : OS (средняя)
    - Хорошее состояние
    Цена : 590€ (в другой валюте по запросу)

    Связь / покупка : @aktavis_eu
    #вналичии

The shop now prices in EUR; older posts used "999 zł / 275 USDT". The
parser extracts EUR, PLN and USDT independently, so any combination works
and legacy zł/USDT posts keep parsing.

Parser is tolerant to small variations:
    - "Цена :590€" (no space) and "Цена : 1 200 €" (thousands separator)
    - "-Новый" without space after dash
    - "*Примечание : ..." prefix
    - "🔊VERY RARE🔊" marker
    - trailing notes after the price, e.g. "590€ (в другой валюте по запросу)"
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from database.models import ProductCategory

logger = logging.getLogger(__name__)


# Order matters — longer / more specific brands must come first so they
# match before their substring.
KNOWN_BRANDS: tuple[str, ...] = (
    "Stone Island x Supreme",
    "Maison Margiela",
    "Louis Vuitton",
    "C.P. Company",
    "Stone Island",
    "Off-White",
    "Saint Laurent",
    "Bottega Veneta",
    "Tom Ford",
    "Maison Kitsuné",
    "Loro Piana",
    "Brunello Cucinelli",
    "Ami Paris",
    "Polo Ralph Lauren",
    "Ralph Lauren",
    "Tommy Hilfiger",
    "Calvin Klein",
    "Hugo Boss",
    "New Balance",
    "The North Face",
    "North Face",
    "Arc'teryx",
    "Patagonia",
    "Yohji Yamamoto",
    "Comme des Garçons",
    "Celine",
    "Moncler",
    "Gucci",
    "Prada",
    "Versace",
    "Dior",
    "Fendi",
    "Burberry",
    "Givenchy",
    "Loewe",
    "Hermes",
    "Chanel",
    "Balenciaga",
    "Supreme",
    "Nike",
    "Adidas",
    "Jordan",
    "Yeezy",
    "Y-3",
    "Lacoste",
    "Armani",
)

CATEGORY_KEYWORDS: dict[ProductCategory, tuple[str, ...]] = {
    ProductCategory.SHOES: (
        "тапочк", "trainer", "skate", "sneak", "boot", "loaf",
        "крос", "shoe", "обув", "сандал", "босонож", "ботин", "мокас",
    ),
    ProductCategory.BAGS: (
        "сумк", "клатч", "рюкзак", "backpack", "tote", "пояс",
    ),
    ProductCategory.JACKETS: (
        "куртк", "ветровк", "пуховик", "пальто", "плащ", "жилет",
        "пиджак", "бомбер", "парк", "анорак", "шуб",
    ),
    ProductCategory.PANTS: (
        "штан", "брюк", "джинс", "pants", "trousers", "jeans",
        "шорт", "shorts",
    ),
    ProductCategory.TOPS: (
        "худи", "кофт", "свитшот", "лонгслив", "футболк", "майк",
        "поло", "толстовк", "свитер", "джемпер", "пуловер", "рубашк",
    ),
    ProductCategory.ACCESSORIES: (
        "часы", "кольц", "очки", "ремень", "кошел", "шапк",
        "перчатк", "watch", "scarf", "шарф", "брелок", "браслет",
        "кепк", "панам",
    ),
}


SIZE_RE = re.compile(r"Размер\s*[:：\-]?\s*([^\n]+)", re.IGNORECASE)
PRICE_PLN_RE = re.compile(
    r"Цена\s*[:：\-]?\s*([\d\s,.]+)\s*z[łl]",
    re.IGNORECASE,
)
# USDT and EUR are extracted independently so we tolerate Markdown
# remnants like "1450 zł** **/ 350 USDT" or "3800 zł / 900€" left by
# Telegram in the post caption.
PRICE_USDT_RE = re.compile(r"(\d[\d\s]*)\s*USDT", re.IGNORECASE)
PRICE_EUR_RE = re.compile(r"(\d[\d\s]*)\s*€")
NOTE_RE = re.compile(
    r"\*?\s*Примечание\s*[:：]\s*([^\n]+(?:\n(?!Связь|Цена|#|$)[^\n]+)*)",
    re.IGNORECASE,
)
CONDITION_RE = re.compile(r"^\s*-\s*(.+)$", re.MULTILINE)
RARE_RE = re.compile(r"VERY\s*RARE", re.IGNORECASE)


def _strip_md(value: str) -> str:
    """Drop stray Markdown bold/italic markers (``*``/``**``) the seller left
    in the caption and collapse the whitespace they leave behind. For
    single-line fields (size, condition, note)."""
    return re.sub(r"\s+", " ", re.sub(r"\*+", "", value)).strip()


SKIP_DESC_PATTERNS = (
    "Связь",
    "связь",
    "#вналичии",
    "#продано",
    "@aktavis_eu",
    "@actavis_eu",
    # Promo footer the admin appends to posts — keep it out of the catalog.
    "БОТ С НАЛИЧИЕМ",
    "t.me/",
)


@dataclass
class ParsedProduct:
    raw_text: str
    title: str
    brand: str
    name: str
    category: ProductCategory
    size: str | None
    condition: str | None
    note: str | None
    price_pln: int | None
    price_usdt: int | None
    price_eur: int | None
    description: str
    is_sold: bool
    is_in_stock: bool

    @property
    def price_primary(self) -> int | None:
        """The canonical price for sorting/display: EUR first, PLN fallback.

        The shop prices in EUR now; ``price_pln`` is kept only so legacy
        zł posts/products still show and sort.
        """
        return self.price_eur or self.price_pln

    @property
    def is_valid(self) -> bool:
        """A post is considered parseable if at least a brand and price exist."""
        return bool(self.brand and self.price_primary)


def _detect_brand(title: str) -> tuple[str, str]:
    """Return ``(brand, name)`` extracted from title.

    Tries to match a known brand and strip it from the title; whatever
    remains becomes the product name.
    Falls back to ``("Unknown", title)`` if no brand recognised.
    """
    lower = title.lower()
    for brand in KNOWN_BRANDS:
        idx = lower.find(brand.lower())
        if idx != -1:
            name = (title[:idx] + title[idx + len(brand):]).strip(" -·,")
            return brand, name or "Item"
    return "Unknown", title


def _detect_category(title: str) -> ProductCategory:
    lower = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    # Fallback: unknown clothing type. Admin can override at preview time.
    return ProductCategory.OTHER


def _parse_price(text: str) -> tuple[int | None, int | None, int | None]:
    pln: int | None = None
    if (m := PRICE_PLN_RE.search(text)):
        try:
            pln = int(re.sub(r"[\s,.]", "", m.group(1)))
        except (ValueError, TypeError):
            pln = None

    usdt: int | None = None
    if (m := PRICE_USDT_RE.search(text)):
        try:
            usdt = int(re.sub(r"\s", "", m.group(1)))
        except (ValueError, TypeError):
            usdt = None

    eur: int | None = None
    if (m := PRICE_EUR_RE.search(text)):
        try:
            eur = int(re.sub(r"\s", "", m.group(1)))
        except (ValueError, TypeError):
            eur = None

    return pln, usdt, eur


def _build_description(text: str) -> str:
    """Strip channel-only lines (contacts, hashtags) but keep product info."""
    cleaned_lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        if any(p in stripped for p in SKIP_DESC_PATTERNS):
            continue
        # Drop Markdown bold markers (`**`) the seller left in the caption.
        stripped = re.sub(r"[ \t]{2,}", " ", re.sub(r"\*+", "", stripped)).strip()
        cleaned_lines.append(stripped)
    description = "\n".join(cleaned_lines).strip()
    description = re.sub(r"\n{3,}", "\n\n", description)
    return description


def parse_channel_post(text: str) -> ParsedProduct | None:
    """Parse a channel-post caption into a :class:`ParsedProduct`.

    Returns ``None`` if the text is empty. Even partially-parseable posts
    yield a ParsedProduct so the admin can decide what to do; check
    ``parsed.is_valid`` for a confidence signal.
    """
    if not text or not text.strip():
        return None

    text = text.replace("\r\n", "\n")
    lower = text.lower()

    is_sold = "#продано" in lower
    is_in_stock = "#вналичии" in lower

    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        return None

    # Strip stray Markdown bold markers (`**`) that sometimes survive in
    # the post caption — they would otherwise end up inside the product
    # name (e.g. "**Тапочки" instead of "Тапочки").
    title = re.sub(r"\*+", "", lines[0])
    title = re.sub(r"\s+", " ", title).strip()
    brand, name = _detect_brand(title)
    category = _detect_category(title)

    size_match = SIZE_RE.search(text)
    size = (_strip_md(size_match.group(1)) or None) if size_match else None

    price_pln, price_usdt, price_eur = _parse_price(text)

    condition: str | None = None
    for cond_candidate in CONDITION_RE.findall(text):
        cleaned = _strip_md(cond_candidate)
        if not cleaned:
            continue
        if cleaned.startswith("#") or "Связь" in cleaned:
            continue
        condition = cleaned
        break

    note_parts: list[str] = []
    note_match = NOTE_RE.search(text)
    if note_match:
        note_parts.append(_strip_md(note_match.group(1)))
    if RARE_RE.search(text):
        note_parts.append("VERY RARE")
    note = " · ".join(note_parts) if note_parts else None

    description = _build_description(text)

    return ParsedProduct(
        raw_text=text,
        title=title,
        brand=brand,
        name=name,
        category=category,
        size=size,
        condition=condition,
        note=note,
        price_pln=price_pln,
        price_usdt=price_usdt,
        price_eur=price_eur,
        description=description,
        is_sold=is_sold,
        is_in_stock=is_in_stock,
    )
