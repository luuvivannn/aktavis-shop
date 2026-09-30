"""Google Sheets report for sales accounting (bot/handlers/accounting.py).

One tab per month ("Сентябрь 2026") with its own colour, a banner, summary
cards and an ИТОГО row. The tab is rebuilt from the ``sales`` table on
every new sale, so it always matches the DB — a sync that failed once heals
itself on the next one. All totals are in EUR: other currencies are
converted in-sheet at the current Google Finance rate.

Best-effort: if GOOGLE_SHEET_ID / GOOGLE_SERVICE_ACCOUNT_JSON aren't
configured, or the API call fails, the caller falls back to "saved in DB,
not synced" rather than losing the accounting entry.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import gspread

from config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_ID

logger = logging.getLogger(__name__)

# Which calendar month a sale lands in.
SALES_TZ = ZoneInfo("Europe/Kyiv")

MONTH_NAMES = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)

# One colour per month so tabs are easy to tell apart. All dark enough for
# white text on top (contrast >= 4.5).
_MONTH_COLORS = {
    1: "#1F4E79",   # navy
    2: "#5B3F8C",   # violet
    3: "#2E7D32",   # green
    4: "#AD1457",   # blossom pink
    5: "#00796B",   # teal
    6: "#9A6B00",   # gold
    7: "#0277BD",   # sea blue
    8: "#C62828",   # red
    9: "#B35A1F",   # autumn amber
    10: "#7B2D43",  # wine
    11: "#455A64",  # slate
    12: "#1B5E20",  # pine
}

_TEXT = "#202124"
_MUTED = "#80868B"
_PROFIT = "#1E7B34"
_WHITE = "#FFFFFF"

# (header, width px, alignment)
_COLUMNS = (
    ("№", 40, "CENTER"),
    ("Дата", 64, "CENTER"),
    ("Бренд", 140, "LEFT"),
    ("Товар", 250, "LEFT"),
    ("Закупка", 84, "RIGHT"),
    ("Вал.", 52, "CENTER"),
    ("Продажа", 84, "RIGHT"),
    ("Вал.", 52, "CENTER"),
    ("Закупка, €", 100, "RIGHT"),
    ("Продажа, €", 100, "RIGHT"),
    ("Прибыль, €", 108, "RIGHT"),
)
_NCOLS = len(_COLUMNS)

# 1-based sheet rows.
_HEADER_ROW = 7
_FIRST_DATA_ROW = 8

# Languages whose locales use '.' as the decimal mark, so formula arguments
# are split by ','. Everywhere else (ru, uk, pl, de…) Sheets expects ';'.
_DOT_DECIMAL_LANGS = {"en", "ja", "zh", "ko", "th", "he", "iw", "hi"}

_EUR_FMT = "#,##0.00"
_PROFIT_FMT = "#,##0.00;[Red]-#,##0.00"

_client: gspread.Client | None = None


@dataclass(frozen=True)
class SaleRow:
    sold_at: datetime  # in SALES_TZ
    brand: str
    name: str
    purchase_amount: Decimal
    purchase_currency: str
    sale_amount: Decimal
    sale_currency: str


def month_title(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month - 1]} {year}"


def _get_spreadsheet() -> gspread.Spreadsheet | None:
    global _client
    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_SHEET_ID:
        return None

    if _client is None:
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        _client = gspread.service_account_from_dict(info)

    return _client.open_by_key(GOOGLE_SHEET_ID)


def _color(hex_color: str, tint: float = 0.0) -> dict:
    """Hex colour as a Sheets colour style, optionally mixed towards white."""
    rgb = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    r, g, b = (c + (1 - c) * tint for c in rgb)
    return {"rgbColor": {"red": r, "green": g, "blue": b}}


def _cell(
    value: str | float | None = None,
    *,
    formula: str | None = None,
    bg: dict | None = None,
    fg: str = _TEXT,
    bold: bool = False,
    size: int = 10,
    align: str = "LEFT",
    valign: str = "MIDDLE",
    number_format: tuple[str, str] | None = None,
    borders: dict | None = None,
) -> dict:
    fmt: dict = {
        "backgroundColorStyle": bg or _color(_WHITE),
        "textFormat": {
            "foregroundColorStyle": _color(fg),
            "fontFamily": "Roboto",
            "fontSize": size,
            "bold": bold,
        },
        "horizontalAlignment": align,
        "verticalAlignment": valign,
        "wrapStrategy": "CLIP",
        "padding": {"left": 6, "right": 6},
    }
    if number_format:
        fmt["numberFormat"] = {"type": number_format[0], "pattern": number_format[1]}
    if borders:
        fmt["borders"] = borders

    cell: dict = {"userEnteredFormat": fmt}
    if formula is not None:
        cell["userEnteredValue"] = {"formulaValue": formula}
    elif isinstance(value, str):
        cell["userEnteredValue"] = {"stringValue": value}
    elif value is not None:
        cell["userEnteredValue"] = {"numberValue": value}
    return cell


def _sheets_serial(dt: datetime) -> float:
    """Local datetime -> Sheets date serial (days since 1899-12-30)."""
    naive = dt.replace(tzinfo=None)
    return (naive - datetime(1899, 12, 30)).total_seconds() / 86400


def _amount_format(amount: Decimal) -> tuple[str, str]:
    return ("NUMBER", "#,##0" if amount == amount.to_integral() else "#,##0.00")


def _to_eur(amount_ref: str, currency_ref: str) -> str:
    return (
        f'=IFERROR({amount_ref}*IF({currency_ref}="EUR",1,'
        f'GOOGLEFINANCE("CURRENCY:"&{currency_ref}&"EUR")),"")'
    )


def _build_grid(title: str, primary: str, sales: list[SaleRow]) -> list[dict]:
    """RowData for the whole tab, A1 downwards."""
    card_bg = _color(primary, 0.86)
    band_bg = _color(primary, 0.94)
    head_bg = _color(primary)
    first, last = _FIRST_DATA_ROW, _FIRST_DATA_ROW + len(sales) - 1
    total = last + 1

    def row(cells: list[dict]) -> dict:
        return {"values": cells}

    def filler(bg: dict | None = None) -> list[dict]:
        return [_cell(bg=bg) for _ in range(_NCOLS)]

    rows: list[dict] = []

    # 1: banner
    banner = filler(head_bg)
    banner[0] = _cell(
        title.upper(), bg=head_bg, fg=_WHITE, bold=True, size=18, align="CENTER"
    )
    rows.append(row(banner))

    # 2: subtitle
    subtitle = filler(card_bg)
    subtitle[0] = _cell(
        "AKTAVIS.EU  ·  учёт продаж  ·  суммы в € по текущему курсу Google",
        bg=card_bg, fg=primary, size=9, align="CENTER",
    )
    rows.append(row(subtitle))

    # 3: spacer
    rows.append(row(filler()))

    # 4–5: summary cards (label over value)
    # A thick white right border on each card's last column reads as a gap
    # between cards (gridlines are hidden).
    gap = {"right": {"style": "SOLID_THICK", "colorStyle": _color(_WHITE)}}
    labels, values = filler(), filler()
    for start, end, label, formula, number_format, accent in _cards(first, last, total):
        bg = head_bg if accent else card_bg
        for col in range(start, end):
            edge = gap if col == end - 1 and end < _NCOLS else None
            if col == start:
                labels[col] = _cell(
                    label, bg=bg, fg=_WHITE if accent else primary, bold=True,
                    size=9, align="CENTER", valign="BOTTOM", borders=edge,
                )
                values[col] = _cell(
                    formula=formula, bg=bg, fg=_WHITE if accent else _TEXT,
                    bold=True, size=16, align="CENTER",
                    number_format=number_format, borders=edge,
                )
            else:
                labels[col] = _cell(bg=bg, borders=edge)
                values[col] = _cell(bg=bg, borders=edge)
    rows.append(row(labels))
    rows.append(row(values))

    # 6: spacer
    rows.append(row(filler()))

    # 7: table header
    rows.append(row([
        _cell(name, bg=head_bg, fg=_WHITE, bold=True, align=align)
        for name, _, align in _COLUMNS
    ]))

    # 8…: one row per sale
    for i, sale in enumerate(sales):
        r = first + i
        bg = band_bg if i % 2 else None
        rows.append(row([
            _cell(i + 1, bg=bg, fg=_MUTED, align="CENTER"),
            _cell(_sheets_serial(sale.sold_at), bg=bg, align="CENTER",
                  number_format=("DATE", "dd.mm")),
            _cell(sale.brand, bg=bg, bold=True),
            _cell(sale.name, bg=bg),
            _cell(float(sale.purchase_amount), bg=bg, align="RIGHT",
                  number_format=_amount_format(sale.purchase_amount)),
            _cell(sale.purchase_currency, bg=bg, fg=_MUTED, align="CENTER"),
            _cell(float(sale.sale_amount), bg=bg, align="RIGHT",
                  number_format=_amount_format(sale.sale_amount)),
            _cell(sale.sale_currency, bg=bg, fg=_MUTED, align="CENTER"),
            _cell(formula=_to_eur(f"E{r}", f"F{r}"), bg=bg, align="RIGHT",
                  number_format=("NUMBER", _EUR_FMT)),
            _cell(formula=_to_eur(f"G{r}", f"H{r}"), bg=bg, align="RIGHT",
                  number_format=("NUMBER", _EUR_FMT)),
            _cell(formula=f'=IF(OR(I{r}="",J{r}=""),"",J{r}-I{r})', bg=bg,
                  fg=_PROFIT, bold=True, align="RIGHT",
                  number_format=("NUMBER", _PROFIT_FMT)),
        ]))

    # last: ИТОГО
    line = {"top": {"style": "SOLID_MEDIUM", "colorStyle": head_bg}}
    totals = [_cell(bg=card_bg, borders=line) for _ in range(_NCOLS)]
    totals[0] = _cell("ИТОГО", bg=card_bg, fg=primary, bold=True, size=11, borders=line)
    for col, letter in ((8, "I"), (9, "J")):
        totals[col] = _cell(
            formula=f"=SUM({letter}{first}:{letter}{last})", bg=card_bg, bold=True,
            size=11, align="RIGHT", number_format=("NUMBER", _EUR_FMT), borders=line,
        )
    totals[10] = _cell(
        formula=f"=SUM(K{first}:K{last})", bg=card_bg, fg=_PROFIT, bold=True,
        size=11, align="RIGHT", number_format=("NUMBER", _PROFIT_FMT), borders=line,
    )
    rows.append(row(totals))
    return rows


def _cards(first: int, last: int, total: int):
    """(start col, end col, label, formula, number format, accent)."""
    return (
        (0, 3, "ПРОДАНО", f"=COUNT(E{first}:E{last})", ("NUMBER", '0 "шт."'), False),
        (3, 4, "ЗАКУПКА", f"=I{total}", ("NUMBER", '#,##0 "€"'), False),
        (4, 8, "ПРОДАЖА", f"=J{total}", ("NUMBER", '#,##0 "€"'), False),
        (8, 10, "ПРИБЫЛЬ", f"=K{total}", ("NUMBER", '#,##0 "€";-#,##0 "€"'), True),
        (10, 11, "МАРЖА", f'=IFERROR(K{total}/J{total},"")', ("PERCENT", "0%"), False),
    )


def _localize_formulas(grid: list[dict], locale: str) -> None:
    """Sheets parses API formulas in the spreadsheet's locale, so a ru_RU
    sheet rejects ``IF(a,b,c)`` and needs ``IF(a;b;c)``. Our formulas are
    written with ',' and have no commas inside string literals."""
    if locale.split("_")[0] in _DOT_DECIMAL_LANGS:
        return
    for row in grid:
        for cell in row["values"]:
            value = cell.get("userEnteredValue", {})
            if "formulaValue" in value:
                value["formulaValue"] = value["formulaValue"].replace(",", ";")


def build_month_requests(
    sheet_id: int, year: int, month: int, sales: list[SaleRow], locale: str = "en_US"
) -> list[dict]:
    """batchUpdate requests that (re)draw the whole month tab."""
    primary = _MONTH_COLORS[month]
    grid = _build_grid(month_title(year, month), primary, sales)
    _localize_formulas(grid, locale)
    total = len(grid)  # ИТОГО is the last row

    def span(r0: int, r1: int, c0: int, c1: int) -> dict:
        return {
            "sheetId": sheet_id,
            "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1,
        }

    merges = [span(0, 1, 0, _NCOLS), span(1, 2, 0, _NCOLS), span(total - 1, total, 0, 4)]
    for start, end, *_ in _cards(_FIRST_DATA_ROW, total - 1, total):
        if end - start > 1:
            merges += [span(3, 4, start, end), span(4, 5, start, end)]

    heights = {0: 46, 1: 24, 2: 10, 3: 24, 4: 38, 5: 14, _HEADER_ROW - 1: 30}
    heights.update({r: 28 for r in range(_FIRST_DATA_ROW - 1, total - 1)})
    heights[total - 1] = 34

    requests: list[dict] = [
        {"unmergeCells": {"range": {"sheetId": sheet_id}}},
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "tabColorStyle": _color(primary),
                    "gridProperties": {
                        "rowCount": total,
                        "columnCount": _NCOLS,
                        "frozenRowCount": 0,
                        "hideGridlines": True,
                    },
                },
                "fields": "tabColorStyle,gridProperties.rowCount,"
                "gridProperties.columnCount,gridProperties.frozenRowCount,"
                "gridProperties.hideGridlines",
            }
        },
        {
            "updateCells": {
                "rows": grid,
                "fields": "userEnteredValue,userEnteredFormat",
                "start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
            }
        },
        *({"mergeCells": {"range": m, "mergeType": "MERGE_ALL"}} for m in merges),
    ]
    for col, (_, width, _) in enumerate(_COLUMNS):
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                          "startIndex": col, "endIndex": col + 1},
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })
    for r, px in sorted(heights.items()):
        requests.append({
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "ROWS",
                          "startIndex": r, "endIndex": r + 1},
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        })
    return requests


def sync_month(year: int, month: int, sales: list[SaleRow]) -> None:
    """Redraw the month's tab from ``sales`` (creating it if needed).

    Blocking network call — run via asyncio.to_thread from handlers.
    """
    if not sales:
        return

    spreadsheet = _get_spreadsheet()
    if spreadsheet is None:
        logger.info("Google Sheets not configured — skipping sales sync")
        return

    title = month_title(year, month)
    try:
        worksheet = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        # Newest month first.
        worksheet = spreadsheet.add_worksheet(
            title, rows=len(sales) + _HEADER_ROW + 1, cols=_NCOLS, index=0
        )

    requests = build_month_requests(
        worksheet.id, year, month, sales, spreadsheet.locale or "en_US"
    )
    spreadsheet.batch_update({"requests": requests})
    logger.info("Sales sheet '%s' synced (%d sales)", title, len(sales))
