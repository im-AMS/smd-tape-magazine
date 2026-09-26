"""Sticker artwork for SMD tape magazines.

Two stickers per part, both the width of the cartridge:
  front  W x 11 mm   on the small chamfer at the dispensing end
  strip  W x 37 mm   on the angled top edge

W = tape size (8 / 12 / 16). Lengths are fixed; only the width tracks the feeder.
"""
from __future__ import annotations
import argparse, csv, html, pathlib, re, sys
from dataclasses import dataclass, field
import segno
from typeset import face, fit, SANS, MONO

# ---------------------------------------------------------------- geometry (mm)
FRONT_L, STRIP_L = 11.0, 37.0
PAGE_W, PAGE_H = 210.0, 297.0
MARGIN_X = 10.0         # inkjets manage the sides fine
MARGIN_Y = 20.0         # the trailing edge is what clips — keep well clear
FOOTER_Y = PAGE_H - 20.0
QR_MAX = 9.0            # never larger than this even on a 16 mm strip
QR_PAD = 0.3            # white between the QR and the sticker edge
GUTTER = 0.25           # gap between stickers; the cut runs down its middle

# Bleed: each sticker's edge colour is extended by half the gutter, so the gap
# between two stickers is filled with their own colours rather than white. A cut
# that drifts then shows colour at the edge instead of a white sliver, which
# reads as a printing fault. The QR needs no special case — nothing coloured is
# allowed near it, so its bleed is white, which is exactly what a quiet zone is.
BAND_H = 2.95           # package band; sized so the package type can breathe
BAR_SHARE = 0.11875     # strip colour bar = 11.875 % of the tape width (0.95 mm on 8 mm)
BAR_MAX = 2.5           # ...but never taller than this, so wide tapes don't get a slab


def strip_bar(w: float) -> float:
    """Strip colour bar height: proportional to the tape width, capped at BAR_MAX."""
    return min(BAR_SHARE * w, BAR_MAX)

# Sizes chosen from the printed experiment sheet (glossy sticker stock, MP tray,
# best quality) rather than from theory. Codes refer to that sheet.
VALUE_SIZE = 3.2        # V32
PKG_SIZE = 2.6          # P26
SUB_SIZE = 2.3
REPEAT_SIZE = 2.15      # strip line 1 — a repeat of the front sticker, so demoted
HEAD_SIZE = 2.6         # strip line 2 — the spec, which is what the strip is for
DETAIL_SIZE = 1.85      # D18L
DETAIL_FLOOR = 1.7      # D17L — legible, used only when 1.85 will not fit
DETAIL_INK = "#7A8380"  # the light grey of D18L, not the darker D18D
WRAP_BELOW = 2.6        # a multi-word value this small is better set on two lines

VALUE_SCALE = (2.0, 2.4, 2.8, 3.2, 3.6, 4.0)   # still used for the wrap decision

CLASS_COLOUR = {
    "R": "#C0761A", "C": "#1E6CAE", "L": "#2C7A58", "D": "#BB3A2C",
    "Q": "#6B4B9B", "U": "#2B3540", "J": "#0D8382", "X": "#68716F",
}
PASSIVE = set("RCL")
# LCSC: the bare domain redirects to www, but the path is case-sensitive (an
# uppercase path lands on the catalogue), so alphanumeric mode is out. 35 bytes
# is still a version 3 symbol (29 modules; version 2 holds 32), 0.255 mm per
# module in the 7.4 mm box an 8 mm strip allows.
#
# If 0.255 mm does not scan reliably on your printer, the remaining lever is a
# redirect host you own:
#     --qr-template "HTTP://EXAMPLE.COM/{sku}"     version 1, ~0.35 mm
# serving a 301 from /<SKU> to the supplier page. See README.
#
# Link patterns, each checked by opening a real part in a browser. No https://
# and no www.: every character costs QR density, and the browser adds them.
# (Check with qr_scan_test_sheet.py that your phone opens scheme-less links.)
SUPPLIERS = {                                   # key: lower-case, no spaces/dashes
    "lcsc":    ("LCSC",    "lcsc.com/product-detail/{sku}.html"),
    "digikey": ("DigiKey", "digikey.com/en/products/result?keywords={sku}"),
    "mouser":  ("Mouser",  "mouser.com/ProductDetail/{sku}"),
}
SUPPLIER = "LCSC"       # used for rows whose supplier cell is empty
QR_TEMPLATE = SUPPLIERS["lcsc"][1]
QR_ECC = "L"            # L keeps the symbol one version smaller than M for long URLs
# Smallest QR module that still scans reliably. Measured on the QR scan test
# sheet (inkjet, iPhone camera): 0.336 mm scanned easily, 0.269 mm failed once,
# 0.248 mm only with effort. Below this a part gets a loud warning.
QR_MIN_MODULE = 0.25


def supplier_key(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())

warnings: list[str] = []


def warn(row: int, msg: str) -> None:
    warnings.append(f"row {row}: {msg}")


# ---------------------------------------------------------------- data
@dataclass
class Part:
    row: int
    cls: str = "X"
    value: str = ""
    pkg: str = ""
    sub: str = ""
    headline: str = ""
    detail: str = ""
    ipn: str = ""
    sku: str = ""
    feeder: float = 8.0
    qr: str = ""
    headline_is_mpn: bool = False

    @property
    def colour(self) -> str:
        return CLASS_COLOUR.get(self.cls, CLASS_COLOUR["X"])


KIND_TO_CLASS = {"R": "R", "RES": "R", "C": "C", "CAP": "C", "L": "L", "IND": "L",
                 "LED": "D", "D": "D", "DIODE": "D", "ESD": "D", "TVS": "D",
                 "Q": "Q", "FET": "Q", "U": "U", "IC": "U", "J": "J", "CONN": "J"}
_CAP_UNIT = {"p": "pF", "n": "nF", "u": "µF", "µ": "µF", "m": "mF", "f": "F"}


def norm_value(cls: str, v: str) -> str:
    v = (v or "").strip()
    if not v:
        return ""
    if cls == "C":
        m = re.fullmatch(r"([\d.]+)\s*([pnuµmf])F?", v, re.I)
        if m:
            return m.group(1) + _CAP_UNIT[m.group(2).lower()]
    if cls == "R":
        if re.fullmatch(r"[\d.]+", v):          # bare ohms -> RKM suffix
            return v + "R"
        m = re.fullmatch(r"([\d.]+)\s*([kKMR])\s*", v)
        if m:
            return m.group(1) + m.group(2).upper().replace("K", "k")
    return v


def norm_rating(cls: str, rating: str) -> str:
    r = (rating or "").strip()
    if not r:
        return ""
    if cls == "R":
        m = re.fullmatch(r"([\d.]+)\s*m", r, re.I)
        return f"{m.group(1)}mW" if m else r
    return re.sub(r"\b(\d+(?:\.\d+)?)\s*v\b", lambda m: m.group(1) + "V", r, flags=re.I)


def voltage_of(rating: str) -> str:
    m = re.search(r"(\d+(?:\.\d+)?)\s*v\b", rating or "", re.I)
    return f"{m.group(1)}V" if m else ""


COLUMNS = ("kind", "value", "tolerance", "rating", "subtype", "footprint", "supplier",
           "sku", "url", "quantity", "feeder")
REQUIRED = ("kind", "value")
ALIASES = {"package": "footprint", "qty": "quantity", "tape_width": "feeder"}


class CsvError(Exception):
    pass


XLSX_SHEET = "parts"     # sheet read from a workbook; the first sheet if there is none


def _cell_text(c) -> str:
    """A spreadsheet cell as the text it displays: 1% is stored as 0.01, 8 as 8.0."""
    v = c.value
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        if "%" in (c.number_format or ""):
            return f"{v * 100:g}%"
        return f"{v:g}"
    return str(v)


def _read_rows(path: pathlib.Path) -> list[list[str]]:
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True)
        ws = wb[XLSX_SHEET] if XLSX_SHEET in wb.sheetnames else wb.worksheets[0]
        return [[_cell_text(c) for c in row] for row in ws.iter_rows()]
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.reader(fh))


def read_columns(path: pathlib.Path) -> list[dict]:
    """Rows as dicts keyed by column name, from a .csv or an .xlsx workbook.
    Columns are matched by header name, in any order, case-insensitive; optional
    columns may be missing entirely."""
    rows = _read_rows(path)
    if not rows:
        return []
    names = [h.strip().lower().replace(" ", "_") for h in rows[0]]
    names = [ALIASES.get(n, n) for n in names]
    dupes = sorted({n for n in names if n and names.count(n) > 1})
    if dupes:
        raise CsvError(f"{path}: column(s) {', '.join(dupes)} appear more than once in "
                       f"the header; rename them so each column has one name")
    missing = [c for c in REQUIRED if c not in names]
    if missing:
        raise CsvError(f"{path}: missing required column(s) {', '.join(missing)}. "
                       f"Known columns: {', '.join(COLUMNS)}")
    unknown = [h for h, n in zip(rows[0], names) if n and n not in COLUMNS]
    if unknown:
        warnings.append(f"ignored column(s): {', '.join(unknown)}")
    out = []
    for i, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        d = {c: "" for c in COLUMNS}
        for n, v in zip(names, r):
            if n in d:
                d[n] = v.strip()
        d["_row"] = i
        out.append(d)
    return out


def load_csv(path: pathlib.Path, feeder: float, qr_template: str | None = None,
             supplier: str = SUPPLIER) -> list[Part]:
    """Read a parts list (see COLUMNS). `feeder`, `supplier` and `qr_template` apply
    to rows whose own cells are empty; qr_template None means the supplier's
    built-in link pattern."""
    out: list[Part] = []
    for d in read_columns(path):
        i = d["_row"]
        kind, value, tol, rating = d["kind"], d["value"], d["tolerance"], d["rating"]
        subtype, fp, sku = d["subtype"], d["footprint"], d["sku"].upper()
        w = feeder
        if d["feeder"]:
            try:
                w = float(d["feeder"].lower().removesuffix("mm").strip())
            except ValueError:
                raise CsvError(f"row {i}: feeder {d['feeder']!r} is not a number (mm)")
            if w <= 0:
                raise CsvError(f"row {i}: feeder must be greater than 0, got {w:g}")
        cls = KIND_TO_CLASS.get(kind.upper(), "X")
        if kind and cls == "X":
            warn(i, f"unknown kind {kind!r}, filed as misc")
        p = Part(row=i, cls=cls, feeder=w, sku=sku, ipn=sku)
        p.value = norm_value(cls, value)
        if not p.value:
            p.value = kind.upper() or "?"
            warn(i, f"no value, using {p.value!r}")
        p.pkg = fp
        rating_n = norm_rating(cls, rating)
        if cls == "R":
            p.sub = rating_n          # power, not tolerance: 2.05 bits vs 0.65
            p.headline = " ".join(x for x in (tol, rating_n, fp) if x)
        elif cls == "C":
            p.sub = voltage_of(rating)
            p.headline = " ".join(x for x in (rating_n, subtype, tol) if x)
        else:
            p.sub = tol or ""
            p.headline = " ".join(x for x in (value, subtype, fp) if x)
        # Stock quantity is deliberately NOT printed — it goes stale the moment
        # you use a part, and a sticker outlives the count.
        if d["supplier"]:
            name, template = SUPPLIERS.get(supplier_key(d["supplier"]), (d["supplier"], None))
            if supplier_key(name) == "other":
                name = ""
        else:
            name = supplier
            template = qr_template or SUPPLIERS.get(supplier_key(supplier), ("", None))[1]
        p.detail = " ".join(x for x in (name, sku) if x) if sku else ""
        if d["url"]:
            p.qr = d["url"]
        elif sku and template:
            p.qr = template.format(sku=sku)
        elif sku:
            warn(i, f"no link for supplier {d['supplier'] or supplier!r}: put the product link "
                    f"in the url column, or the sticker has no QR")
        else:
            warn(i, "no SKU or url, sticker will have no QR")
        out.append(p)
    return out


# ---------------------------------------------------------------- drawing
def esc(s) -> str:
    return html.escape(str(s), quote=True)


def text(s: str, x: float, y: float, size: float, fill: str, mono: bool = False,
         anchor: str = "start", xscale: float = 1.0, outline: bool = True,
         opacity: float | None = None) -> str:
    name = MONO if mono else SANS
    op = f' opacity="{opacity}"' if opacity is not None else ""
    if not outline:
        fam = "IBM Plex Mono" if mono else "Barlow Semi Condensed"
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        return (f'<text x="{x:.3f}" y="{y:.3f}" font-family="{fam}" font-weight="700" '
                f'font-size="{size:.3f}" fill="{fill}"{a}{op}>{esc(s)}</text>')
    f = face(name)
    w = f.width(s, size) * xscale
    ox = {"start": 0.0, "middle": -w / 2, "end": -w}[anchor]
    d = f.path(s, size, xscale)
    if not d:
        return ""
    return (f'<g transform="translate({x + ox:.3f},{y:.3f})"{op}>'
            f'<path d="{d}" fill="{fill}"/></g>')


def qr_svg(payload: str, size: float, x: float, y: float, ecc: str = QR_ECC):
    q = segno.make(payload, error=ecc, micro=False)
    n = q.symbol_size(border=0)[0]
    u = size / n
    d, matrix = [], q.matrix
    for yy, rowv in enumerate(matrix):
        xx = 0
        while xx < n:
            if rowv[xx]:
                x0 = xx
                while xx < n and rowv[xx]:
                    xx += 1
                d.append(f"M{x0} {yy}h{xx - x0}v1h-{xx - x0}z")
            else:
                xx += 1
    g = (f'<g transform="translate({x:.3f},{y:.3f}) scale({u:.6f})">'
         f'<path d="{"".join(d)}" fill="#111"/></g>')
    return g, n, u


# ---------------------------------------------------------------- type planning
def step_for(s: str, name: str, box: float, scale, squeeze: float = 0.80):
    """Largest step in `scale` that fits `s` into `box`.

    Returns (size, xscale) or None when even the smallest step needs more
    compression than `squeeze` allows.
    """
    f = face(name)
    for size in reversed(scale):
        if f.width(s, size) <= box:
            return size, 1.0
    small = scale[0]
    w = f.width(s, small)
    if w and box / w >= squeeze:
        return small, box / w
    return None


def wrap_two(s: str):
    """Split on the space nearest the middle; failing that, after the hyphen
    nearest the middle, keeping the hyphen so a part number is never shortened
    (USBLC6-2SC6 -> "USBLC6-" / "2SC6"). None when there is nothing to split."""
    mid = len(s) / 2
    spaces = [i for i, ch in enumerate(s) if ch == " "]
    if spaces:
        best = min(spaces, key=lambda i: abs(i - mid))
        return s[:best], s[best + 1:]
    hyphens = [i for i, ch in enumerate(s) if ch == "-" and 0 < i < len(s) - 1]
    if hyphens:
        best = min(hyphens, key=lambda i: abs(i + 1 - mid))
        return s[:best + 1], s[best + 1:]
    return None


@dataclass
class Style:
    """The sizes picked off the printed experiment sheet."""
    value: float = VALUE_SIZE
    pkg: float = PKG_SIZE
    sub: float = SUB_SIZE
    repeat: float = REPEAT_SIZE
    head: float = HEAD_SIZE
    detail: float = DETAIL_SIZE


def plan(parts: list[Part], feeder: float) -> Style:
    """Sizes are fixed by the experiment; strings that will not fit are demoted
    individually by _fit_step rather than shrinking the whole sheet."""
    return Style()


cut_log: list[tuple[str, str]] = []   # (original, as it would print) for every shortened string


def _fit_step(s: str, name: str, box: float, size: float, squeeze: float = 0.80,
              floor: float | None = None):
    """Set `s` at `size` if it fits, else compress, else drop a step, else ellipsise.
    Anything it had to shorten is recorded in cut_log."""
    f = face(name)
    w = f.width(s, size)
    if w <= box:
        return size, 1.0, s, None
    if box / w >= squeeze:
        return size, box / w, s, None
    size2, xs, t, d = fit(s, name, box, size, floor or size * 0.62)
    if t != s:
        cut_log.append((s, t))
    return size2, xs, t, d


def text_cuts(p: "Part", st: "Style") -> list[tuple[str, str]]:
    """Strings on this part's stickers that would print shortened."""
    cut_log.clear()
    draw_front(p, st)
    draw_strip(p, st)
    return list(cut_log)


def stack(lines, zone_top, zone_bot, x, box, gap=0.55, anchor="start"):
    """Lay out lines as one optically centred block between zone_top and zone_bot.

    Positions come from real cap heights, so the block sits centred rather than
    hanging off whichever edge the baselines were measured from.
    """
    f = face(SANS)
    fitted = [(_fit_step(t, SANS, box, sz,
                         floor=DETAIL_FLOOR if sz == DETAIL_SIZE else None), fill)
              for t, sz, fill in lines if t]
    caps = [f.cap_height(r[0][0]) for r in fitted]
    total = sum(caps) + gap * (len(caps) - 1)
    y = zone_top + (zone_bot - zone_top - total) / 2
    out = []
    for (size, xs, t, _), fill in fitted:
        cap = f.cap_height(size)
        y += cap
        out.append(text(t, x, y, size, fill, anchor=anchor, xscale=xs))
        y += gap
    return "".join(out)


# ---------------------------------------------------------------- drawing
def draw_front(p: Part, st: Style, bleed: float = 0.0) -> str:
    """Package band across the top, value centred in what is left, qualifier below."""
    W, L = p.feeder, FRONT_L
    box = W - 1.4
    f = face(SANS)
    z = bleed
    b = [f'<rect x="{-z}" y="{-z}" width="{W + 2*z}" height="{L + 2*z}" fill="#fff"/>',
         f'<rect x="{-z}" y="{-z}" width="{W + 2*z}" height="{BAND_H + z}" fill="{p.colour}"/>']
    if p.pkg:
        size, xs, t, d = _fit_step(p.pkg, SANS, W - 1.4, st.pkg)
        base = BAND_H / 2 + f.cap_height(size) / 2          # optically centred in the band
        b.append(text(t, W / 2, base, size, "#fff", anchor="middle", xscale=xs))

    sub_base = L - 0.75
    if p.sub:
        sub_size, sub_xs, sub_t, _ = _fit_step(p.sub, SANS, box, st.sub)
        zone_bot = sub_base - f.cap_height(sub_size) - 0.55
    else:
        zone_bot = L - 0.7
    zone_top = BAND_H + 0.15

    lines, size = [p.value], st.value
    got = step_for(p.value, SANS, box, VALUE_SCALE)
    if got is None or got[0] < WRAP_BELOW:
        pair = wrap_two(p.value)
        if pair:
            # Two lines: never larger than the one-line design size, and small
            # enough that both lines fit between the band and the qualifier.
            two = min(st.value, min((step_for(x, SANS, box, VALUE_SCALE) or (VALUE_SCALE[0], 1.0))[0]
                                    for x in pair))
            steps = [s for s in VALUE_SCALE if s <= two]
            fits = [s for s in steps if s * 1.16 + f.cap_height(s) <= zone_bot - zone_top]
            if fits:
                lines, size = list(pair), fits[-1]

    if len(lines) == 1:
        size, xs, t, d = _fit_step(p.value, SANS, box, st.value)
        if d:
            warn(p.row, f"value {d}")
        cap = f.cap_height(size)
        base = zone_top + (zone_bot - zone_top + cap) / 2     # centred, not bottom-aligned
        b.append(text(t, W / 2, base, size, "#111", anchor="middle", xscale=xs))
    else:
        lead = size * 1.16
        cap = f.cap_height(size)
        block = lead * (len(lines) - 1) + cap
        y0 = zone_top + (zone_bot - zone_top - block) / 2 + cap
        for i, ln in enumerate(lines):
            s2, xs2, t2, _ = _fit_step(ln, SANS, box, size)
            b.append(text(t2, W / 2, y0 + i * lead, s2, "#111", anchor="middle", xscale=xs2))

    if p.sub:
        b.append(text(sub_t, W / 2, sub_base, sub_size, p.colour, anchor="middle", xscale=sub_xs))
    return "".join(b)


def draw_strip(p: Part, st: Style, bleed: float = 0.0) -> str:
    """Layout B: a plain colour bar, every character on white.

    Line 1 repeats the front sticker so it is demoted; line 2 is the spec, which
    is the only thing on this sticker the front one does not already tell you.
    """
    W, L = p.feeder, STRIP_L
    qs = min(W - 2 * QR_PAD, QR_MAX) if p.qr else 0.0
    tw = L - (qs + 1.2) if p.qr else L - 0.8
    bar = strip_bar(W)
    z = bleed
    b = [f'<rect x="{-z}" y="{-z}" width="{L + 2*z}" height="{W + 2*z}" fill="#fff"/>',
         f'<rect x="{-z}" y="{-z}" width="{tw + z:.3f}" height="{bar + z}" fill="{p.colour}"/>']
    repeat = " · ".join(x for x in (p.value, p.pkg) if x)
    b.append(stack([(repeat, st.repeat, "#3B4447"),
                    (p.headline, st.head, "#111"),
                    (p.detail, st.detail, DETAIL_INK)],
                   bar + 0.15, W - 0.45, 0.9, tw - 1.8, gap=0.5))
    if p.qr:
        g, n, u = qr_svg(p.qr, qs, L - qs - QR_PAD, (W - qs) / 2)
        b.append(g)
    return "".join(b)


# ---------------------------------------------------------------- sheet
# Every sticker cell is the same height (front + strip); only its width varies
# with the feeder. A cut runs down the middle of each gutter.
CELL_H_EXTRA = 7.0      # space kept above the footer
ROW_GAP = 8.0           # row/mixed layouts: room for each row's own cut ticks
LAYOUTS = {
    "page":  "one width per page: every column lines up down the whole sheet",
    "row":   "one width per row: rows may differ, a row never mixes widths",
    "mixed": "mix widths freely: tightest packing, any widths side by side",
}


def usable_w() -> float:
    return PAGE_W - 2 * MARGIN_X


def cell_h(gutter: float) -> float:
    return FRONT_L + STRIP_L + 2 * gutter


def grid(feeder: float, gutter: float):
    """Column pitch, cell pitch and counts for a single-width page."""
    px = feeder + gutter
    py = cell_h(gutter)
    cols = int(usable_w() // px)
    rows = int((FOOTER_Y - CELL_H_EXTRA - MARGIN_Y) // py)
    return px, py, cols, rows


def rows_per_page_gapped(gutter: float) -> int:
    py = cell_h(gutter)
    return max(1, int((FOOTER_Y - CELL_H_EXTRA - MARGIN_Y + ROW_GAP) // (py + ROW_GAP)))


def tick(t: list, x1, y1, x2, y2, w=0.22):
    t.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
             f'stroke="#111" stroke-width="{w}"/>')


def cut_ticks(ox, oy, gw, gh, cols, rows, px, py, gutter):
    """Ticks in the margins only — a printed line would land on a sticker edge."""
    t = []
    for c in range(cols + 1):
        x = ox + c * px
        tick(t, x, oy - 4.5, x, oy - 0.9)
        tick(t, x, oy + gh + 0.9, x, oy + gh + 4.5)
    for r in range(rows + 1):
        y = oy + r * py
        tick(t, ox - 4.5, y, ox - 0.9, y)
        tick(t, ox + gw + 0.9, y, ox + gw + 4.5, y)
    for r in range(rows):                      # short ticks: front / strip split
        y = oy + r * py + FRONT_L + gutter
        tick(t, ox - 2.4, y, ox - 0.9, y, 0.18)
        tick(t, ox + gw + 0.9, y, ox + gw + 2.4, y, 0.18)
    return "".join(t)


def footer(label: str) -> str:
    """Optional. Off by default — the cut ticks already give a measurable span."""
    by = FOOTER_Y
    o = [f'<line x1="{MARGIN_X}" y1="{by}" x2="{MARGIN_X + 50}" y2="{by}" stroke="#111" stroke-width="0.3"/>']
    for i in range(6):
        o.append(f'<line x1="{MARGIN_X + i * 10}" y1="{by - 1.8}" x2="{MARGIN_X + i * 10}" y2="{by}" '
                 f'stroke="#111" stroke-width="0.3"/>')
    o.append(text("50.0 mm — measure before trusting this sheet", MARGIN_X + 53, by, 2.6,
                  "#555", mono=True))
    o.append(text(label, PAGE_W - MARGIN_X, by, 2.6, "#555", mono=True, anchor="end"))
    return "".join(o)


def svg_open() -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
            f'viewBox="0 0 {PAGE_W} {PAGE_H}"><rect width="{PAGE_W}" height="{PAGE_H}" fill="#fff"/>')


def place(p: Part, st: Style, x: float, y: float, gutter: float) -> str:
    """One cell: front sticker on top, strip below it (rotated to run down the cell)."""
    x, y = x + gutter / 2, y + gutter / 2
    ys = y + FRONT_L + gutter
    return (f'<g transform="translate({x:.3f},{y:.3f})">{draw_front(p, st, gutter / 2)}</g>'
            f'<g transform="translate({x:.3f},{ys:.3f}) rotate(-90) '
            f'translate({-STRIP_L},0)">{draw_strip(p, st, gutter / 2)}</g>')


def render_sheet(parts, st: Style, feeder: float, gutter: float,
                 page_no: int, pages: int, marks: bool = False) -> str:
    """Single-width page: a uniform grid, every cut a straight full-sheet cut."""
    px, py, cols, rows = grid(feeder, gutter)
    gw = cols * px
    ox, oy = (PAGE_W - gw) / 2, MARGIN_Y      # top-aligned: keeps the footer printable
    o = [svg_open()]
    for i, p in enumerate(parts):
        c, r = i % cols, i // cols
        o.append(place(p, st, ox + c * px, oy + r * py, gutter))
    # Ticks only for rows that carry stickers: a tick next to an empty row
    # invites a cut through blank stock that could still be printed on later.
    used = max(1, -(-len(parts) // cols))
    o.append(cut_ticks(ox, oy, gw, used * py, cols, used, px, py, gutter))
    if marks:
        o.append(footer(f"{feeder:g} mm feeder · {len(parts)} parts · page {page_no}/{pages}"))
    o.append("</svg>")
    return "".join(o)


def render_rows(rows: list[list[Part]], st: Style, gutter: float,
                label: str, marks: bool = False) -> str:
    """Rows of varying widths, separated by ROW_GAP.

    Columns no longer line up between rows, so each row carries its own vertical
    cut ticks, in the gap just above and just below it. Horizontal cuts still run
    the full sheet, guided by ticks in the side margins. Cut on the intact sheet
    (through the sticker layer only), so every tick stays usable.
    """
    py = cell_h(gutter)
    widths = [sum(p.feeder + gutter for p in r) for r in rows]
    gw = max(widths)
    ox, oy = (PAGE_W - gw) / 2, MARGIN_Y
    o, t = [svg_open()], []
    for r, row in enumerate(rows):
        y = oy + r * (py + ROW_GAP)
        x = ox
        edges = [x]
        for p in row:
            o.append(place(p, st, x, y, gutter))
            x += p.feeder + gutter
            edges.append(x)
        for ex in edges:                       # this row's column cuts
            tick(t, ex, y - 0.9, ex, y - 3.2)
            tick(t, ex, y + py + 0.9, ex, y + py + 3.2)
        for yy, short in ((y, False), (y + FRONT_L + gutter, True), (y + py, False)):
            ln, w = (2.4, 0.18) if short else (4.5, 0.22)
            tick(t, ox - ln, yy, ox - 0.9, yy, w)
            tick(t, ox + gw + 0.9, yy, ox + gw + ln, yy, w)
    o.append("".join(t))
    if marks:
        o.append(footer(label))
    o.append("</svg>")
    return "".join(o)


def next_fit(parts: list[Part], gutter: float, same_width: bool) -> list[list[Part]]:
    """Fill rows in the given order; start a new row when the next sticker does
    not fit (or, with same_width, when its width differs from the row's)."""
    rows, cur, used = [], [], 0.0
    for p in parts:
        w = p.feeder + gutter
        if cur and (used + w > usable_w() or (same_width and p.feeder != cur[0].feeder)):
            rows.append(cur); cur, used = [], 0.0
        cur.append(p); used += w
    if cur:
        rows.append(cur)
    return rows


def first_fit_decreasing(parts: list[Part], gutter: float) -> list[list[Part]]:
    """Tightest simple packing: widest first, each into the first row with room."""
    rows, used = [], []
    for p in sorted(parts, key=lambda p: -p.feeder):
        w = p.feeder + gutter
        for i, u in enumerate(used):
            if u + w <= usable_w():
                rows[i].append(p); used[i] += w
                break
        else:
            rows.append([p]); used.append(w)
    return rows


def by_width(parts: list[Part]) -> list[list[Part]]:
    """Group by feeder width, groups in order of first appearance, CSV order within."""
    groups: dict[float, list[Part]] = {}
    for p in parts:
        groups.setdefault(p.feeder, []).append(p)
    return list(groups.values())


def pack(parts: list[Part], gutter: float, layout: str):
    """Rows for the row/mixed layouts. CSV order is kept whenever it costs no
    extra rows; otherwise the tighter packing is used. Returns (rows, reordered)."""
    if layout == "mixed":
        ordered = next_fit(parts, gutter, same_width=False)
        tight = first_fit_decreasing(parts, gutter)
    else:
        ordered = next_fit(parts, gutter, same_width=True)
        tight = next_fit([p for g in by_width(parts) for p in g], gutter, same_width=True)
    return (ordered, False) if len(ordered) <= len(tight) else (tight, True)


def paginate(parts, feeder: float, gutter: float):
    _, _, cols, rows = grid(feeder, gutter)
    per = cols * rows
    return [parts[i:i + per] for i in range(0, len(parts), per)] or [[]]


def qr_check(parts: list[Part]):
    """("error", part, msg) when a link cannot be encoded at all; ("small", part,
    msg) when its modules come out below QR_MIN_MODULE on that part's strip."""
    out = []
    for p in parts:
        if not p.qr:
            continue
        try:
            q = segno.make(p.qr, error=QR_ECC, micro=False)
        except segno.DataOverflowError:
            out.append(("error", p, f"link is {len(p.qr)} characters, too long for any QR code"))
            continue
        n = q.symbol_size(border=0)[0]
        box = min(p.feeder - 2 * QR_PAD, QR_MAX)
        u = box / n
        if u < QR_MIN_MODULE:
            out.append(("small", p, f"{len(p.qr)}-character link -> {n} modules in a {box:g} mm box "
                                    f"= {u:.3f} mm per module (limit {QR_MIN_MODULE} mm)"))
    return out


def ask_layout() -> str | None:
    """None when the user quits (Ctrl-D / Ctrl-C) instead of answering."""
    keys = list(LAYOUTS)
    print("\nThis parts list has more than one feeder width. How should they share sheets?")
    for i, k in enumerate(keys, 1):
        print(f"  {i}. {k:6} {LAYOUTS[k]}")
    while True:
        try:
            a = input(f"Choose 1-{len(keys)} (or pass --layout to skip this question): ")
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        a = a.strip().lower()
        if a in keys:
            return a
        if a.isdigit() and 1 <= int(a) <= len(keys):
            return keys[int(a) - 1]
        print("  not one of the options")


# ---------------------------------------------------------------- cli
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=pathlib.Path, help="parts CSV")
    ap.add_argument("-o", "--out", type=pathlib.Path, default=pathlib.Path("out"))
    ap.add_argument("--feeder", type=float, default=8.0,
                    help="tape width in mm for rows with no feeder column/value (default 8)")
    ap.add_argument("--layout", choices=list(LAYOUTS),
                    help="how mixed feeder widths share sheets; asked interactively if omitted")
    ap.add_argument("--gutter", type=float, default=GUTTER,
                    help=f"white between stickers in mm (default {GUTTER}); cuts run down its middle")
    ap.add_argument("--qr-template", default=None,
                    help="QR link pattern for rows with no supplier cell; {sku} is substituted "
                         "(default: the built-in pattern of --supplier)")
    ap.add_argument("--supplier", default=SUPPLIER,
                    help="supplier for rows whose supplier cell is empty (default: LCSC)")
    ap.add_argument("--marks", action="store_true",
                    help="add a 50 mm ruler and footer; off by default so no ink is spent on words")
    ap.add_argument("--pdf", action="store_true", help="also write PDF via inkscape")
    a = ap.parse_args()

    try:
        parts = load_csv(a.input, a.feeder, a.qr_template, a.supplier)
    except CsvError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not parts:
        print("no parts found", file=sys.stderr)
        return 1
    too_wide = [p for p in parts if p.feeder + a.gutter > usable_w()]
    if too_wide:
        for p in too_wide:
            print(f"error: row {p.row}: a {p.feeder:g} mm sticker does not fit the "
                  f"{usable_w():g} mm printable width", file=sys.stderr)
        return 1

    widths = sorted({p.feeder for p in parts})
    layout = a.layout or "page"
    if len(widths) > 1 and not a.layout:
        if not sys.stdin.isatty():
            print(f"error: feeder widths {', '.join(f'{w:g}' for w in widths)} mm are mixed; "
                  f"choose --layout {{{','.join(LAYOUTS)}}}", file=sys.stderr)
            return 1
        layout = ask_layout()
        if layout is None:
            print("no layout chosen, nothing written", file=sys.stderr)
            return 1

    st = plan(parts, a.feeder)
    qr_problems = qr_check(parts)
    if any(kind == "error" for kind, *_ in qr_problems):
        for kind, p, msg in qr_problems:
            if kind == "error":
                print(f"error: row {p.row}: {msg}", file=sys.stderr)
        print("Nothing was written.", file=sys.stderr)
        return 1
    # Never print a shortened value: a cut part number is worse than no sticker.
    bad = [(p, c) for p in parts if (c := text_cuts(p, st))]
    if bad:
        for p, cuts in bad:
            print(f"error: row {p.row}: {p.value!r} does not fit a {p.feeder:g} mm sticker",
                  file=sys.stderr)
            for orig, shown in cuts:
                print(f"         {orig!r} would print as {shown!r}", file=sys.stderr)
        print("Shorten these values in the CSV (or use a wider feeder). Nothing was written.",
              file=sys.stderr)
        return 1
    a.out.mkdir(parents=True, exist_ok=True)
    sheets: list[tuple[pathlib.Path, str, int]] = []
    notes: list[str] = []
    if layout == "page":
        for group in by_width(parts):
            w = group[0].feeder
            pages = paginate(group, w, a.gutter)
            for n, page in enumerate(pages, 1):
                f = a.out / f"sheet_{w:g}mm_{n:02d}.svg"
                sheets.append((f, render_sheet(page, st, w, a.gutter, n, len(pages), a.marks), len(page)))
            px, _, cols, rows = grid(w, a.gutter)
            notes.append(f"{w:g} mm: {len(group)} parts · {cols}×{rows} = {cols * rows} per sheet · "
                         f"scale check: outermost column ticks {cols * px:.2f} mm apart")
    else:
        rows, reordered = pack(parts, a.gutter, layout)
        per = rows_per_page_gapped(a.gutter)
        pages = [rows[i:i + per] for i in range(0, len(rows), per)]
        for n, page in enumerate(pages, 1):
            f = a.out / f"sheet_{layout}_{n:02d}.svg"
            label = f"{layout} layout · page {n}/{len(pages)}"
            sheets.append((f, render_rows(page, st, a.gutter, label, a.marks), sum(map(len, page))))
        w0 = sum(p.feeder + a.gutter for p in rows[0])
        notes.append(f"{len(rows)} row(s), {per} per sheet · "
                     f"{'reordered to save rows' if reordered else 'CSV order kept'} · "
                     f"scale check: row 1 outermost ticks {w0:.2f} mm apart")

    written = []
    for f, svg, n in sheets:
        f.write_text(svg, encoding="utf-8")
        written.append(f)
        print(f"{f}  —  {n} parts")

    if a.pdf:
        import subprocess
        for f in written:
            pdf = f.with_suffix(".pdf")
            subprocess.run(["inkscape", "--export-type=pdf", f"--export-filename={pdf}", str(f)],
                           check=True, capture_output=True)
            print(f"{pdf}")

    print(f"\n{len(parts)} parts · layout: {layout} · {len(written)} sheet(s)")
    for n in notes:
        print(n)
    print(f"type: value {st.value} mm · pkg {st.pkg} · sub {st.sub} · "
          f"headline {st.head} · detail {st.detail}  (gutter {a.gutter} mm)")
    for w in widths:
        p = next((p for p in parts if p.feeder == w and p.qr), None)
        if p:
            q = segno.make(p.qr, error=QR_ECC, micro=False)
            n = q.symbol_size(border=0)[0]
            qs = min(w - 2 * QR_PAD, QR_MAX)
            print(f"QR @ {w:g} mm: {q.mode} mode, version {q.version}, {n} modules, "
                  f"{qs:.1f} mm box → {qs / n:.3f} mm per module")
    small = [(p, msg) for kind, p, msg in qr_problems if kind == "small"]
    if small:
        bar = "!" * 78
        print(f"\n{bar}\n  QR WARNING: {len(small)} sticker(s) have QR codes that may not scan\n{bar}",
              file=sys.stderr)
        for p, msg in small:
            print(f"  row {p.row} ({p.value}): {msg}", file=sys.stderr)
        print(f"  Shorter link, or wider tape. Test with qr_scan_test_sheet.py before "
              f"printing a full sheet.\n{bar}", file=sys.stderr)
    if warnings:
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"  {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
