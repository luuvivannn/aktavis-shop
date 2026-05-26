"""Parser for Telegram channel posts in the AKTAVIS.EU format.

Expected post layout (Russian):

    Ветровка C.P. Company
    Размер : L
    - Идеальное состояние
    Цена : 999 zł / 275 USDT

    Связь / покупка : @aktavis_eu

    #вналичии

Parser is tolerant to small variations:
    - "Цена :1450 zł" (no space) and "Цена : 1 450 zł" (thousands separator)
    - "-Новый" without space after dash
    - "*Примечание : ..." prefix
    - "🔊VERY RARE🔊" marker
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
PRICE_RE = re.compile(
    r"Цена\s*[:：\-]?\s*([\d\s,.]+)\s*z[łl]\s*"
    r"(?:/\s*(\d[\d\s]*)\s*USDT)?",
    re.IGNORECASE,
)
NOTE_RE = re.compile(
    r"\*?\s*Примечание\s*[:：]\s*([^\n]+(?:\n(?!Связь|Цена|#|$)[^\n]+)*)",
    re.IGNORECASE,
)
CONDITION_RE = re.compile(r"^\s*-\s*(.+)$", re.MULTILINE)
RARE_RE = re.compile(r"VERY\s*RARE", re.IGNORECASE)

SKIP_DESC_PATTERNS = (
    "Связь",
    "связь",
    "#вналичии",
    "#продано",
    "@aktavis_eu",
    "@actavis_eu",
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
    description: str
    is_sold: bool
    is_in_stock: bool

    @property
    def is_valid(self) -> bool:
        """A post is considered parseable if at least a brand and price exist."""
        return bool(self.brand and self.price_pln)


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


def _parse_price(text: str) -> tuple[int | None, int | None]:
    match = PRICE_RE.search(text)
    if not match:
        return None, None
    pln: int | None = None
    usdt: int | None = None
    try:
        pln = int(re.sub(r"[\s,.]", "", match.group(1)))
    except (ValueError, TypeError):
        pln = None
    if match.group(2):
        try:
            usdt = int(re.sub(r"\s", "", match.group(2)))
        except (ValueError, TypeError):
            usdt = None
    return pln, usdt


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

    title = re.sub(r"\s+", " ", lines[0]).strip()
    brand, name = _detect_brand(title)
    category = _detect_category(title)

    size_match = SIZE_RE.search(text)
    size = size_match.group(1).strip() if size_match else None

    price_pln, price_usdt = _parse_price(text)

    condition: str | None = None
    for cond_candidate in CONDITION_RE.findall(text):
        cleaned = cond_candidate.strip()
        if not cleaned:
            continue
        if cleaned.startswith("#") or "Связь" in cleaned:
            continue
        condition = cleaned
        break

    note_parts: list[str] = []
    note_match = NOTE_RE.search(text)
    if note_match:
        note_parts.append(note_match.group(1).strip())
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
        description=description,
        is_sold=is_sold,
        is_in_stock=is_in_stock,
    )
