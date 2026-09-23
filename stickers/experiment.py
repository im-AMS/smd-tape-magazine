"""One A4 that settles every open question about the sticker design.

Each cell is coded (A1, K18, V28 …) so results can be reported without
ambiguity. Everything is at 1:1 and uses real parts from the inventory.
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from labels import (load_csv, plan, qr_svg, text, _fit_step, CLASS_COLOUR, stack,
                    PAGE_W, PAGE_H, QR_TEMPLATE, QR_PAD, QR_MAX, STRIP_L,
                    FRONT_L, draw_front, SUPPLIER, BAND_H)
from typeset import SANS, face

M = 14.0
W = 8.0
QS = min(W - 2 * QR_PAD, QR_MAX)
TW = STRIP_L - (QS + 1.2)
o = []
CUT = "#B9C0BD"          # cut marks: visible against white, invisible once cut through
EDGE = "#E4E8E6"         # sticker outline, lighter still


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


def mono(s, x, y, size, fill="#111", anchor="start"):
    return text(s, x, y, size, fill, mono=True, anchor=anchor)


def sans(s, x, y, size, fill="#111", box=None, anchor="start", xs=1.0):
    if box:
        size, xs, s, _ = _fit_step(s, SANS, box, size)
    return text(s, x, y, size, fill, anchor=anchor, xscale=xs)


def head(y, code, title):
    o.append(mono(code, M, y, 3.0))
    o.append(mono(title, M + 9, y, 2.7, "#444"))


def tint(hex_colour, pct):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    f = lambda c: round(c + (255 - c) * (1 - pct))
    return f"#{f(r):02x}{f(g):02x}{f(b):02x}"


# ---------------------------------------------------------------- strip variants
LAYOUTS = {
    "A": "A  knockout rule (today)",
    "B": "B  colour bar — repeat line smaller, spec larger",
    "E": "E  colour bar — both lines equal",
    "C": "C  colour rail",
    "F": "F  colour rail, no repeat line — spec gets the room",
}


def strip(p, kind, x, y):
    col = p.colour
    g = [f'<rect width="{STRIP_L}" height="{W}" fill="#fff"/>']
    repeat = f"{p.value} · {p.pkg}"
    if kind == "A":
        g.append(f'<rect width="{TW:.2f}" height="2.15" fill="{col}"/>')
        g.append(sans(repeat, 0.9, 1.6, 1.95, "#fff", TW * 0.92))
        g.append(stack([(p.headline, 2.9, "#111"), (p.detail, 2.0, "#5A6461")],
                       2.3, W - 0.5, 0.9, TW - 1.8))
    elif kind in ("B", "E"):
        s1, s2 = (2.15, 2.6) if kind == "B" else (2.45, 2.45)
        g.append(f'<rect width="{TW:.2f}" height="0.95" fill="{col}"/>')
        g.append(stack([(repeat, s1, "#3B4447"), (p.headline, s2, "#111"),
                        (p.detail, 1.85, "#7A8380")], 1.1, W - 0.5, 0.9, TW - 1.8, gap=0.5))
    elif kind == "C":
        cw = 2.0
        g.append(f'<rect width="{cw}" height="{W}" fill="{col}"/>')
        g.append(stack([(repeat, 2.75, "#111"), (p.headline, 2.2, "#3B4447"),
                        (p.detail, 1.85, "#7A8380")], 0.4, W - 0.4, cw + 1.0,
                       TW - cw - 1.6, gap=0.5))
    else:                                   # F — the repeat line dropped entirely
        cw = 2.0
        g.append(f'<rect width="{cw}" height="{W}" fill="{col}"/>')
        g.append(stack([(p.headline, 3.2, "#111"), (p.detail, 2.1, "#5A6461")],
                       0.4, W - 0.4, cw + 1.0, TW - cw - 1.6, gap=0.8))
    qg, n, u = qr_svg(p.qr, QS, STRIP_L - QS - QR_PAD, (W - QS) / 2)
    g.append(qg)
    o.append(f'<g transform="translate({x},{y})">{"".join(g)}'
             f'<rect width="{STRIP_L}" height="{W}" fill="none" stroke="{EDGE}" '
             f'stroke-width="0.1"/></g>')
    o.append(crop(x, y, STRIP_L, W))


def build():
    parts = load_csv(pathlib.Path(sys.argv[1]), W, QR_TEMPLATE)
    st = plan(parts, W)
    by = {p.value: p for p in parts}
    sel = [by.get("330R", parts[0]), by.get("100nF", parts[12]), by.get("RED", parts[19])]

    o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
             f'viewBox="0 0 {PAGE_W} {PAGE_H}"><rect width="{PAGE_W}" height="{PAGE_H}" fill="#fff"/>')
    o.append(mono("Sticker design experiment — one sheet, every open question", M, 20, 4.0))
    for i, l in enumerate([
        "Print 100%, best quality, on the stock you intend to use. Check the 50 mm ruler at the bottom.",
        "Judge at arm's length (~400 mm), not nose to paper. Report the codes.",
        "Sections 1, 3 and 6 carry light grey cut marks — cut some out for practice before the real sheet.",
    ]):
        o.append(mono(l, M, 26 + i * 4.0, 2.4, "#444"))

    # -- 1 strip layouts
    head(40, "1", "strip layout — every text block is now optically centred")
    y = 46.5
    for r, kind in enumerate("ABECF"):
        o.append(mono(LAYOUTS[kind], M, y + r * 14.5 - 3.2, 2.4, "#111"))
        for c, p in enumerate(sel):
            strip(p, kind, M + c * 45.5, y + r * 14.5)
            o.append(mono(f"{kind}{c+1}", M + c * 45.5 + 39.6, y + r * 14.5 + 5.4, 2.2, "#666"))
    y = y + 5 * 14.5 + 3

    # -- 2 reverse type
    head(y, "2", "reverse type — where does white-on-colour stop being crisp?")
    y += 5
    col = CLASS_COLOUR["R"]
    for i, size in enumerate([1.8, 2.0, 2.2, 2.4]):
        yy = y + i * 5.2
        for j, (bg, fg, code) in enumerate([(col, "#fff", "K"), ("#fff", "#111", "P"),
                                            (tint(col, 0.22), "#6a3d05", "T")]):
            xx = M + j * 58
            o.append(f'<rect x="{xx}" y="{yy}" width="48" height="4.2" fill="{bg}" '
                     f'stroke="{"#ddd" if bg == "#fff" else bg}" stroke-width="0.1"/>')
            o.append(sans("330R · 0603 · 1% 100mW", xx + 0.9, yy + 3.1, size, fg, 46))
            o.append(mono(f"{code}{int(size*10)}", xx + 49.5, yy + 3.1, 2.2, "#666"))
    for j, lbl in enumerate(["white on solid", "black on white", "dark on 22% tint"]):
        o.append(mono(lbl, M + j * 58, y - 1.2, 2.1, "#666"))
    y += 4 * 5.2 + 3

    # -- 3 front sticker: value size (left) and package size (right)
    head(y, "3", "front sticker — value size V, package size P")
    y += 8.5
    for i, size in enumerate([2.4, 2.8, 3.2, 3.6]):
        for j, p in enumerate(sel[:2]):
            st2 = plan([p], W); st2.value = size
            xx = M + i * 22.4 + j * 9.2
            o.append(f'<g transform="translate({xx},{y})">{draw_front(p, st2)}'
                     f'<rect width="{W}" height="{FRONT_L}" fill="none" stroke="{EDGE}" '
                     f'stroke-width="0.1"/></g>')
            o.append(crop(xx, y, W, FRONT_L))
        o.append(mono(f"V{int(size*10)}", M + i * 22.4, y + FRONT_L + 3.2, 2.2, "#666"))
    for i, size in enumerate([2.0, 2.2, 2.4, 2.6]):
        p = sel[0]
        st2 = plan([p], W); st2.pkg = size
        xx = M + 100 + i * 10.6
        o.append(f'<g transform="translate({xx},{y})">{draw_front(p, st2)}'
                 f'<rect width="{W}" height="{FRONT_L}" fill="none" stroke="{EDGE}" '
                 f'stroke-width="0.1"/></g>')
        o.append(crop(xx, y, W, FRONT_L))
        o.append(mono(f"P{int(size*10)}", xx, y + FRONT_L + 3.2, 2.2, "#666"))
    o.append(mono("value size (today V28)", M, y - 3.6, 2.1, "#666"))
    o.append(mono("package size (today P26)", M + 100, y - 3.6, 2.1, "#666"))
    y += FRONT_L + 7

    # -- 4 detail line
    head(y, "4", "detail line — smallest size and lightest grey that still reads")
    y += 4.5
    for i, (size, fill, code) in enumerate([
            (1.7, "#7A8380", "D17L"), (1.85, "#7A8380", "D18L"), (2.0, "#7A8380", "D20L"),
            (1.7, "#3B4447", "D17D"), (1.85, "#3B4447", "D18D"), (2.0, "#3B4447", "D20D")]):
        xx = M + (i // 3) * 90
        yy = y + (i % 3) * 4.6
        o.append(sans(f"{SUPPLIER} R178998 · 1% 100mW 0603", xx, yy, size, fill, 70))
        o.append(mono(code, xx + 73, yy, 2.2, "#666"))
    y += 3 * 4.6 + 1

    # -- 5 class colours
    head(y, "5", "class colours — do these stay distinct on your stock?")
    y += 4.5
    for i, (k, hexv) in enumerate(CLASS_COLOUR.items()):
        xx = M + i * 22
        o.append(f'<rect x="{xx}" y="{y}" width="20" height="9" fill="{hexv}"/>')
        o.append(sans(k, xx + 1.2, y + 3.4, 2.4, "#fff"))
        o.append(sans("330R", xx + 1.2, y + 7.6, 2.4, "#fff"))
        o.append(mono(hexv, xx, y + 11.8, 1.9, "#666"))
    y += 16

    # -- 6 cutting
    head(y, "6", "cutting — knife and ruler on all three. Which gutter?")
    y += 5
    for gi, gut in enumerate([0.2, 0.3, 0.5]):
        x0 = M + gi * 58
        o.append(mono(f"G{int(gut*10):02d}  gutter {gut} mm", x0, y - 1.0, 2.3, "#111"))
        for c in range(5):
            for r in range(2):
                o.append(f'<g transform="translate({x0 + c*(W+gut)},{y + 1.5 + r*(FRONT_L+gut)})">'
                         f'{draw_front(sel[c % 3], st)}</g>')
        gw = 5 * (W + gut) - gut
        gh = 2 * FRONT_L + gut
        for c in range(6):
            xx = x0 + c * (W + gut) - gut / 2
            o.append(f'<line x1="{xx:.2f}" y1="{y+0.1}" x2="{xx:.2f}" y2="{y+1.1}" '
                     f'stroke="{CUT}" stroke-width="0.16"/>')
            o.append(f'<line x1="{xx:.2f}" y1="{y+1.9+gh:.2f}" x2="{xx:.2f}" '
                     f'y2="{y+2.9+gh:.2f}" stroke="{CUT}" stroke-width="0.16"/>')
        for r in range(3):
            yy = y + 1.5 + r * (FRONT_L + gut) - gut / 2
            o.append(f'<line x1="{x0-1.6:.2f}" y1="{yy:.2f}" x2="{x0-0.6:.2f}" y2="{yy:.2f}" '
                     f'stroke="{CUT}" stroke-width="0.16"/>')
            o.append(f'<line x1="{x0+gw+0.6:.2f}" y1="{yy:.2f}" x2="{x0+gw+1.6:.2f}" '
                     f'y2="{yy:.2f}" stroke="{CUT}" stroke-width="0.16"/>')
    y += 2 * FRONT_L + 9

    o.append(mono("Report: strip layout (A/B/E/C/F) · smallest crisp cell in row 2 (K/P/T) ·", M, y + 4, 2.5))
    o.append(mono("V code · P code · smallest readable D code · colours that collide · G02 G03 or G05",
                  M, y + 8, 2.5))
    by_ = y + 16
    o.append(f'<line x1="{M}" y1="{by_}" x2="{M+50}" y2="{by_}" stroke="#111" stroke-width="0.3"/>')
    for i in range(6):
        o.append(f'<line x1="{M+i*10}" y1="{by_-2}" x2="{M+i*10}" y2="{by_}" stroke="#111" stroke-width="0.3"/>')
    o.append(mono("50.0 mm — if this is not 50 mm the print was rescaled", M + 53, by_, 2.5))
    o.append("</svg>")
    out = pathlib.Path(__file__).parent / "out" / "experiment_A4.svg"
    out.write_text("".join(o), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    build()
