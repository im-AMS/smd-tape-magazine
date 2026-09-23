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
# Shortest LCSC URL that still lands on the product page: the bare domain
# redirects to www, but the path is case-sensitive (an uppercase path lands on
# the catalogue), so alphanumeric mode is out. 43 bytes is a version 3 symbol
# (29 modules), 0.255 mm per module in the 7.4 mm box an 8 mm strip allows.
#
# If 0.255 mm does not scan reliably on your printer, the remaining lever is a
# redirect host you own:
#     --qr-template "HTTP://EXAMPLE.COM/{sku}"     version 1, ~0.35 mm
# serving a 301 from /<SKU> to the supplier page. See README.
#
# Any other supplier works through --supplier and --qr-template, e.g. Robu:
#     --supplier Robu --qr-template "https://robu.in/?s={sku}&post_type=product"
QR_TEMPLATE = "https://lcsc.com/product-detail/{sku}.html"
QR_ECC = "L"            # L keeps the symbol one version smaller than M for long URLs
SUPPLIER = "LCSC"       # printed on the strip alongside the SKU

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


def load_csv(path: pathlib.Path, feeder: float, qr_template: str,
             supplier: str = SUPPLIER) -> list[Part]:
    """Read a parts list.

    Columns are taken by position, not name (some exports repeat a header):
    kind, value, tolerance, rating, subtype, footprint, sku, quantity
    """
    out: list[Part] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    for i, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        r = (r + [""] * 8)[:8]
        kind, value, tol, rating, subtype, fp, sku, qty = (c.strip() for c in r)
        cls = KIND_TO_CLASS.get(kind.upper(), "X")
        if kind and cls == "X":
            warn(i, f"unknown kind {kind!r}, filed as misc")
        p = Part(row=i, cls=cls, feeder=feeder, sku=sku.upper(), ipn=sku.upper())
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
        p.detail = f"{supplier} {sku.upper()}" if sku else ""
        p.qr = qr_template.format(sku=sku.upper()) if sku else ""
        if not sku:
            warn(i, "no SKU, sticker will have no QR")
        out.append(p)
    return out


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
    """Split on the space nearest the middle. None when there is nothing to split."""
    if " " not in s:
        return None
    mid, best = len(s) / 2, None
    for i, ch in enumerate(s):
        if ch == " " and (best is None or abs(i - mid) < abs(best - mid)):
            best = i
    return s[:best], s[best + 1:]


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


def _fit_step(s: str, name: str, box: float, size: float, squeeze: float = 0.80,
              floor: float | None = None):
    """Set `s` at `size` if it fits, else compress, else drop a step, else ellipsise."""
    f = face(name)
    w = f.width(s, size)
    if w <= box:
        return size, 1.0, s, None
    if box / w >= squeeze:
        return size, box / w, s, None
    size2, xs, t, d = fit(s, name, box, size, floor or size * 0.62)
    return size2, xs, t, d


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
            lines = list(pair)
            size = min((step_for(x, SANS, box, VALUE_SCALE) or (VALUE_SCALE[0], 1.0))[0]
                       for x in lines)

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
    bar = 0.95
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
def grid(feeder: float, gutter: float):
    """Column pitch, cell pitch and counts. Cuts run down the middle of each gutter."""
    px = feeder + gutter
    py = FRONT_L + STRIP_L + 2 * gutter
    cols = int((PAGE_W - 2 * MARGIN_X) // px)
    rows = int((FOOTER_Y - 7.0 - MARGIN_Y) // py)
    return px, py, cols, rows


def cut_ticks(ox, oy, gw, gh, cols, rows, px, py, gutter):
    """Ticks in the margins only — a printed line would land on a sticker edge."""
    t = []
    def tick(x1, y1, x2, y2, w=0.22):
        t.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                 f'stroke="#111" stroke-width="{w}"/>')
    for c in range(cols + 1):
        x = ox + c * px
        tick(x, oy - 4.5, x, oy - 0.9)
        tick(x, oy + gh + 0.9, x, oy + gh + 4.5)
    for r in range(rows + 1):
        y = oy + r * py
        tick(ox - 4.5, y, ox - 0.9, y)
        tick(ox + gw + 0.9, y, ox + gw + 4.5, y)
    for r in range(rows):                      # short ticks: front / strip split
        y = oy + r * py + FRONT_L + gutter
        tick(ox - 2.4, y, ox - 0.9, y, 0.18)
        tick(ox + gw + 0.9, y, ox + gw + 2.4, y, 0.18)
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


def render_sheet(parts, st: Style, feeder: float, gutter: float,
                 page_no: int, pages: int, marks: bool = False) -> str:
    px, py, cols, rows = grid(feeder, gutter)
    gw, gh = cols * px, rows * py
    ox, oy = (PAGE_W - gw) / 2, MARGIN_Y      # top-aligned: keeps the footer printable
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
         f'viewBox="0 0 {PAGE_W} {PAGE_H}"><rect width="{PAGE_W}" height="{PAGE_H}" fill="#fff"/>']
    for i, p in enumerate(parts):
        c, r = i % cols, i // cols
        x = ox + c * px + gutter / 2
        y = oy + r * py + gutter / 2
        o.append(f'<g transform="translate({x:.3f},{y:.3f})">{draw_front(p, st, gutter / 2)}</g>')
        ys = y + FRONT_L + gutter
        o.append(f'<g transform="translate({x:.3f},{ys:.3f}) rotate(-90) '
                 f'translate({-STRIP_L},0)">{draw_strip(p, st, gutter / 2)}</g>')
    o.append(cut_ticks(ox, oy, gw, gh, cols, rows, px, py, gutter))
    if marks:
        o.append(footer(f"{feeder:g} mm feeder · {len(parts)} parts · page {page_no}/{pages}"))
    o.append("</svg>")
    return "".join(o)


def paginate(parts, feeder: float, gutter: float):
    _, _, cols, rows = grid(feeder, gutter)
    per = cols * rows
    return [parts[i:i + per] for i in range(0, len(parts), per)] or [[]]


# ---------------------------------------------------------------- cli
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=pathlib.Path, help="parts CSV")
    ap.add_argument("-o", "--out", type=pathlib.Path, default=pathlib.Path("out"))
    ap.add_argument("--feeder", type=float, default=8.0, help="tape width in mm (default 8)")
    ap.add_argument("--gutter", type=float, default=GUTTER,
                    help="white between stickers in mm (default 0.5); cuts run down its middle")
    ap.add_argument("--qr-template", default=QR_TEMPLATE,
                    help="QR payload; {sku} is substituted (default: the LCSC product page)")
    ap.add_argument("--supplier", default=SUPPLIER,
                    help="supplier name printed before the SKU (default: LCSC)")
    ap.add_argument("--marks", action="store_true",
                    help="add a 50 mm ruler and footer; off by default so no ink is spent on words")
    ap.add_argument("--pdf", action="store_true", help="also write PDF via inkscape")
    a = ap.parse_args()

    parts = load_csv(a.input, a.feeder, a.qr_template, a.supplier)
    if not parts:
        print("no parts found", file=sys.stderr)
        return 1
    st = plan(parts, a.feeder)
    a.out.mkdir(parents=True, exist_ok=True)
    pages = paginate(parts, a.feeder, a.gutter)
    written = []
    for n, page in enumerate(pages, 1):
        f = a.out / f"sheet_{a.feeder:g}mm_{n:02d}.svg"
        f.write_text(render_sheet(page, st, a.feeder, a.gutter, n, len(pages), a.marks),
                     encoding="utf-8")
        written.append(f)
        print(f"{f}  —  {len(page)} parts")

    if a.pdf:
        import subprocess
        for f in written:
            pdf = f.with_suffix(".pdf")
            subprocess.run(["inkscape", "--export-type=pdf", f"--export-filename={pdf}", str(f)],
                           check=True, capture_output=True)
            print(f"{pdf}")

    px, _, cols, rows = grid(a.feeder, a.gutter)
    print(f"\n{len(parts)} parts · {cols}×{rows} = {cols * rows} per sheet · {len(pages)} sheet(s)")
    print(f"scale check: outermost column ticks must measure {cols * px:.2f} mm apart "
          f"(ticks are {px:.2f} mm apart)")
    print(f"type: value {st.value} mm · pkg {st.pkg} · sub {st.sub} · "
          f"headline {st.head} · detail {st.detail}  (gutter {a.gutter} mm)")
    if parts[0].qr:
        q = segno.make(parts[0].qr, error=QR_ECC, micro=False)
        n = q.symbol_size(border=0)[0]
        qs = min(a.feeder - 2 * QR_PAD, QR_MAX)
        print(f"QR: {q.mode} mode, version {q.version}, {n} modules, "
              f"{qs:.1f} mm box → {qs / n:.3f} mm per module")
    if warnings:
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"  {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
