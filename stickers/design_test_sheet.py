"""Design test sheet: every open question about the sticker design, at 1:1.

Each cell is coded (A1, K18, V28 …) so results can be reported without
ambiguity. Sample stickers are the first parts in the CSV with the chosen
feeder width, so the test prints your own parts at your own tape size.
Sections flow onto extra pages when a wide feeder needs the room.

    uv run design_test_sheet.py parts.csv [--feeder 12] [--supplier …] [--qr-template …]
"""
import argparse, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from labels import (load_csv, plan, qr_svg, text, _fit_step, CLASS_COLOUR, stack,
                    PAGE_W, PAGE_H, QR_PAD, QR_MAX, STRIP_L,
                    FRONT_L, draw_front, SUPPLIER, CsvError)
from typeset import SANS

M = 14.0                 # page side margin
TOP, BOTTOM = 20.0, PAGE_H - 20.0      # inkjets clip the trailing edge
CUT = "#B9C0BD"          # cut marks: visible against white, invisible once cut through
EDGE = "#E4E8E6"         # sticker outline, lighter still
LAYOUTS = {
    "A": "A  knockout rule",
    "B": "B  colour bar — repeat line smaller, spec larger (current)",
    "E": "E  colour bar — both lines equal",
    "C": "C  colour rail",
    "F": "F  colour rail, no repeat line — spec gets the room",
}


def mono(s, x, y, size, fill="#111", anchor="start"):
    return text(s, x, y, size, fill, mono=True, anchor=anchor)


def sans(s, x, y, size, fill="#111", box=None, anchor="start", xs=1.0):
    if box:
        size, xs, s, _ = _fit_step(s, SANS, box, size)
    return text(s, x, y, size, fill, anchor=anchor, xscale=xs)


def crop(x, y, w, h, off=0.45, ln=1.5, col=CUT, sw=0.13):
    """Corner crop marks outside a sticker, so it can be cut out for practice."""
    m = []
    for cx, sx in ((x, -1), (x + w, 1)):
        for cy, sy in ((y, -1), (y + h, 1)):
            m.append(f'<line x1="{cx + sx*off:.2f}" y1="{cy:.2f}" x2="{cx + sx*(off+ln):.2f}" '
                     f'y2="{cy:.2f}" stroke="{col}" stroke-width="{sw}"/>')
            m.append(f'<line x1="{cx:.2f}" y1="{cy + sy*off:.2f}" x2="{cx:.2f}" '
                     f'y2="{cy + sy*(off+ln):.2f}" stroke="{col}" stroke-width="{sw}"/>')
    return "".join(m)


def tint(hex_colour, pct):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    f = lambda c: round(c + (255 - c) * (1 - pct))
    return f"#{f(r):02x}{f(g):02x}{f(b):02x}"


def shade(hex_colour, k):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return f"#{round(r*k):02x}{round(g*k):02x}{round(b*k):02x}"


class Pages:
    """A4 pages with a y cursor; `need` starts a new page when a block won't fit."""

    def __init__(self, title):
        self.title, self.pages = title, []
        self.new()

    def new(self):
        self.o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
                  f'viewBox="0 0 {PAGE_W} {PAGE_H}"><rect width="{PAGE_W}" height="{PAGE_H}" fill="#fff"/>']
        self.pages.append(self.o)
        n = len(self.pages)
        self.o.append(mono(self.title + (f" — page {n}" if n > 1 else ""), M, TOP, 4.0))
        self.y = TOP + 6

    def need(self, h):
        if self.y + h > BOTTOM:
            self.new()

    def add(self, s):
        self.o.append(s)


def head(pg, code, title, h):
    """Section heading, kept on the same page as the first `h` mm of its content."""
    pg.need(6 + h)
    pg.add(mono(code, M, pg.y + 3, 3.0))
    pg.add(mono(title, M + 9, pg.y + 3, 2.7, "#444"))
    pg.y += 6


def strip(p, kind, x, y):
    W = p.feeder
    col = p.colour
    qs = min(W - 2 * QR_PAD, QR_MAX)
    tw = STRIP_L - (qs + 1.2)
    g = [f'<rect width="{STRIP_L}" height="{W}" fill="#fff"/>']
    repeat = f"{p.value} · {p.pkg}" if p.pkg else p.value
    if kind == "A":
        g.append(f'<rect width="{tw:.2f}" height="2.15" fill="{col}"/>')
        g.append(sans(repeat, 0.9, 1.6, 1.95, "#fff", tw * 0.92))
        g.append(stack([(p.headline, 2.9, "#111"), (p.detail, 2.0, "#5A6461")],
                       2.3, W - 0.5, 0.9, tw - 1.8))
    elif kind in ("B", "E"):
        s1, s2 = (2.15, 2.6) if kind == "B" else (2.45, 2.45)
        g.append(f'<rect width="{tw:.2f}" height="0.95" fill="{col}"/>')
        g.append(stack([(repeat, s1, "#3B4447"), (p.headline, s2, "#111"),
                        (p.detail, 1.85, "#7A8380")], 1.1, W - 0.5, 0.9, tw - 1.8, gap=0.5))
    elif kind == "C":
        cw = 2.0
        g.append(f'<rect width="{cw}" height="{W}" fill="{col}"/>')
        g.append(stack([(repeat, 2.75, "#111"), (p.headline, 2.2, "#3B4447"),
                        (p.detail, 1.85, "#7A8380")], 0.4, W - 0.4, cw + 1.0,
                       tw - cw - 1.6, gap=0.5))
    else:                                   # F — the repeat line dropped entirely
        cw = 2.0
        g.append(f'<rect width="{cw}" height="{W}" fill="{col}"/>')
        g.append(stack([(p.headline, 3.2, "#111"), (p.detail, 2.1, "#5A6461")],
                       0.4, W - 0.4, cw + 1.0, tw - cw - 1.6, gap=0.8))
    if p.qr:
        qg, _, _ = qr_svg(p.qr, qs, STRIP_L - qs - QR_PAD, (W - qs) / 2)
        g.append(qg)
    return (f'<g transform="translate({x},{y})">{"".join(g)}'
            f'<rect width="{STRIP_L}" height="{W}" fill="none" stroke="{EDGE}" '
            f'stroke-width="0.1"/></g>' + crop(x, y, STRIP_L, W))


def front(p, st, x, y):
    return (f'<g transform="translate({x:.2f},{y:.2f})">{draw_front(p, st)}'
            f'<rect width="{p.feeder}" height="{FRONT_L}" fill="none" stroke="{EDGE}" '
            f'stroke-width="0.1"/></g>' + crop(x, y, p.feeder, FRONT_L))


def flow(pg, blocks, row_h, gap=6.0):
    """Place fixed-size blocks left to right, wrapping to a new line when the
    page width runs out. Each block is (width, draw(x, y))."""
    x, right = M, PAGE_W - M
    pg.need(row_h)
    for w, draw in blocks:
        if x > M and x + w > right:
            pg.y += row_h
            pg.need(row_h)
            x = M
        pg.add(draw(x, pg.y))
        x += w + gap
    pg.y += row_h


def build(parts, W, out_dir):
    sel = [p for p in parts if p.feeder == W][:3]
    if not sel:
        raise CsvError(f"no parts with a {W:g} mm feeder in the CSV")
    while len(sel) < 3:                     # fewer than three parts: repeat them
        sel.append(sel[len(sel) % len(sel)])
    st = plan(sel, W)
    p0 = sel[0]
    sample = " · ".join(x for x in (p0.value, p0.pkg, p0.headline) if x)
    pg = Pages(f"Sticker design test — {W:g} mm")
    for l in ("Print 100%, best quality, on the stock you intend to use. Check the 50 mm ruler at the end.",
              "Judge at arm's length (~400 mm), not nose to paper. Report the codes.",
              "Sections 1, 3 and 6 carry light grey cut marks — cut some out for practice."):
        pg.add(mono(l, M, pg.y, 2.4, "#444"))
        pg.y += 4.0
    pg.y += 3

    # -- 1 strip layouts: three sample parts per layout
    row_h = W + 6.5
    head(pg, "1", "strip layout", row_h)
    for kind in "ABECF":
        pg.need(row_h)
        pg.add(mono(LAYOUTS[kind], M, pg.y + 0.3, 2.4))
        for c, p in enumerate(sel):
            x = M + c * (STRIP_L + 8.5)
            pg.add(strip(p, kind, x, pg.y + 2.5))
            pg.add(mono(f"{kind}{c+1}", x + STRIP_L + 1.6, pg.y + 2.5 + W / 2 + 0.8, 2.2, "#666"))
        pg.y += row_h
    pg.y += 1

    # -- 2 reverse type, in the first sample's class colour
    col = p0.colour
    head(pg, "2", "reverse type — where does white-on-colour stop being crisp?", 26)
    pg.y += 2
    for j, lbl in enumerate(["white on solid", "black on white", "dark on 22% tint"]):
        pg.add(mono(lbl, M + j * 58, pg.y, 2.1, "#666"))
    pg.y += 1.2
    for i, size in enumerate([1.8, 2.0, 2.2, 2.4]):
        yy = pg.y + i * 5.2
        for j, (bg, fg, code) in enumerate([(col, "#fff", "K"), ("#fff", "#111", "P"),
                                            (tint(col, 0.22), shade(col, 0.55), "T")]):
            xx = M + j * 58
            pg.add(f'<rect x="{xx}" y="{yy}" width="48" height="4.2" fill="{bg}" '
                   f'stroke="{"#ddd" if bg == "#fff" else bg}" stroke-width="0.1"/>')
            pg.add(sans(sample, xx + 0.9, yy + 3.1, size, fg, 46))
            pg.add(mono(f"{code}{int(size*10)}", xx + 49.5, yy + 3.1, 2.2, "#666"))
    pg.y += 4 * 5.2 + 2

    # -- 3 front sticker: value size, then package size
    front_h = FRONT_L + 6.5          # label, sticker, crop marks
    head(pg, "3", "front sticker — value size V, package size P", front_h)
    blocks = []
    for size in (2.4, 2.8, 3.2, 3.6):
        def draw(x, y, size=size):
            s = [mono(f"V{int(size*10)}", x, y + 1.5, 2.2, "#666")]
            for j, p in enumerate(sel[:2]):
                st2 = plan([p], W); st2.value = size
                s.append(front(p, st2, x + j * (W + 1.2), y + 3))
            return "".join(s)
        blocks.append((2 * W + 1.2, draw))
    for size in (2.0, 2.2, 2.4, 2.6):
        def draw(x, y, size=size):
            st2 = plan([p0], W); st2.pkg = size
            return mono(f"P{int(size*10)}", x, y + 1.5, 2.2, "#666") + front(p0, st2, x, y + 3)
        blocks.append((max(W, 8.0), draw))
    flow(pg, blocks, front_h)

    # -- 4 detail line
    detail = " · ".join(x for x in (p0.detail, p0.headline) if x) or sample
    head(pg, "4", "detail line — smallest size and lightest grey that still reads", 15)
    for i, (size, fill, code) in enumerate([
            (1.7, "#7A8380", "D17L"), (1.85, "#7A8380", "D18L"), (2.0, "#7A8380", "D20L"),
            (1.7, "#3B4447", "D17D"), (1.85, "#3B4447", "D18D"), (2.0, "#3B4447", "D20D")]):
        xx = M + (i // 3) * 90
        yy = pg.y + 1.5 + (i % 3) * 4.6
        pg.add(sans(detail, xx, yy, size, fill, 70))
        pg.add(mono(code, xx + 73, yy, 2.2, "#666"))
    pg.y += 3 * 4.6 + 3

    # -- 5 class colours
    head(pg, "5", "class colours — do these stay distinct on your stock?", 14)
    for i, (k, hexv) in enumerate(CLASS_COLOUR.items()):
        xx = M + i * 22
        pg.add(f'<rect x="{xx}" y="{pg.y}" width="20" height="9" fill="{hexv}"/>')
        pg.add(sans(k, xx + 1.2, pg.y + 3.4, 2.4, "#fff"))
        pg.add(sans(p0.value, xx + 1.2, pg.y + 7.6, 2.4, "#fff", 17.6))
        pg.add(mono(hexv, xx, pg.y + 11.8, 1.9, "#666"))
    pg.y += 16

    # -- 6 cutting: 5 x 2 front stickers per gutter width
    cut_h = 2 * FRONT_L + 7.5        # label, two rows, cut ticks
    head(pg, "6", "cutting — knife and ruler on all three. Which gutter?", cut_h)
    blocks = []
    for gut in (0.2, 0.3, 0.5):
        def draw(x0, y, gut=gut):
            s = [mono(f"G{int(gut*10):02d}  gutter {gut} mm", x0, y + 1.0, 2.3)]
            y0 = y + 3.5
            for c in range(5):
                for r in range(2):
                    s.append(f'<g transform="translate({x0 + c*(W+gut):.2f},{y0 + r*(FRONT_L+gut):.2f})">'
                             f'{draw_front(sel[c % 3], st)}</g>')
            gw, gh = 5 * (W + gut) - gut, 2 * FRONT_L + gut
            for c in range(6):
                xx = x0 + c * (W + gut) - gut / 2
                s.append(f'<line x1="{xx:.2f}" y1="{y0-1.4:.2f}" x2="{xx:.2f}" y2="{y0-0.4:.2f}" '
                         f'stroke="{CUT}" stroke-width="0.16"/>')
                s.append(f'<line x1="{xx:.2f}" y1="{y0+gh+0.4:.2f}" x2="{xx:.2f}" '
                         f'y2="{y0+gh+1.4:.2f}" stroke="{CUT}" stroke-width="0.16"/>')
            for r in range(3):
                yy = y0 + r * (FRONT_L + gut) - gut / 2
                s.append(f'<line x1="{x0-1.6:.2f}" y1="{yy:.2f}" x2="{x0-0.6:.2f}" y2="{yy:.2f}" '
                         f'stroke="{CUT}" stroke-width="0.16"/>')
                s.append(f'<line x1="{x0+gw+0.6:.2f}" y1="{yy:.2f}" x2="{x0+gw+1.6:.2f}" '
                         f'y2="{yy:.2f}" stroke="{CUT}" stroke-width="0.16"/>')
            return "".join(s)
        blocks.append((max(5 * (W + gut), 34.0), draw))
    flow(pg, blocks, cut_h, gap=8.0)

    pg.need(18)
    pg.add(mono("Report: strip layout (A/B/E/C/F) · smallest crisp cell in section 2 (K/P/T) ·", M, pg.y + 4, 2.5))
    pg.add(mono("V code · P code · smallest readable D code · colours that collide · G02 G03 or G05",
                M, pg.y + 8, 2.5))
    by_ = pg.y + 16
    pg.add(f'<line x1="{M}" y1="{by_}" x2="{M+50}" y2="{by_}" stroke="#111" stroke-width="0.3"/>')
    for i in range(6):
        pg.add(f'<line x1="{M+i*10}" y1="{by_-2}" x2="{M+i*10}" y2="{by_}" stroke="#111" stroke-width="0.3"/>')
    pg.add(mono("50.0 mm — if this is not 50 mm the print was rescaled", M + 53, by_, 2.5))

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for n, page in enumerate(pg.pages, 1):
        suffix = f"_{n:02d}" if len(pg.pages) > 1 else ""
        f = out_dir / f"design_test_sheet_{W:g}mm_A4{suffix}.svg"
        f.write_text("".join(page) + "</svg>", encoding="utf-8")
        written.append(f)
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=pathlib.Path, help="parts CSV (same format as labels.py)")
    ap.add_argument("-o", "--out", type=pathlib.Path,
                    default=pathlib.Path(__file__).parent / "out")
    ap.add_argument("--feeder", type=float,
                    help="tape width to test, in mm (default: the first part's width)")
    ap.add_argument("--default-feeder", type=float, default=8.0,
                    help="width for rows with no feeder value (default 8)")
    ap.add_argument("--qr-template", default=None,
                    help="link pattern for rows with no supplier cell (default: built-in)")
    ap.add_argument("--supplier", default=SUPPLIER)
    a = ap.parse_args()
    try:
        parts = load_csv(a.input, a.default_feeder, a.qr_template, a.supplier)
        if not parts:
            raise CsvError("no parts found")
        W = a.feeder or parts[0].feeder
        for f in build(parts, W, a.out):
            print(f)
    except CsvError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
