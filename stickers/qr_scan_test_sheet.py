"""Print-and-scan diagnostic for the strip QR.

Row 1 codes are real links built from the SKUs in your CSV with your QR
template, so whatever page your phone opens names the cell that worked. Row 2
is a density probe (text, not a link). Section 3 compares payload variants of
your own URL; section 4 shows real strips at 1:1.

    uv run qr_scan_test_sheet.py parts.csv [--feeder 12] [--supplier …] [--qr-template …]

Everything sits between y=20 and y=277 so nothing lands in a printer's
unprintable trailing-edge margin.
"""
import argparse, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from labels import (draw_strip, qr_svg, text, PAGE_W, PAGE_H, QR_PAD,
                    QR_MAX, SUPPLIER, STRIP_L, load_csv, plan, CsvError)
import segno

M = 15.0
# Row 2 is a DENSITY PROBE, not a link. It measures whether a 21-module symbol
# survives your printer, without pretending to be a URL.
PROBE = "PROBE V1 {size} NOT A LINK"
OFFSETS = (-0.8, -0.4, 0.0, 0.4, 1.0, 1.6)   # QR sizes tried around the strip's own box


def mono(s, x, y, size, fill="#111", anchor="start"):
    return text(s, x, y, size, fill, mono=True, anchor=anchor)


def ruler(o, y, label="50.0 mm — if this is not 50 mm, the print was rescaled"):
    o.append(f'<line x1="{M}" y1="{y}" x2="{M + 50}" y2="{y}" stroke="#111" stroke-width="0.3"/>')
    for i in range(6):
        o.append(f'<line x1="{M + i * 10}" y1="{y - 2}" x2="{M + i * 10}" y2="{y}" '
                 f'stroke="#111" stroke-width="0.3"/>')
    o.append(mono(label, M + 53, y, 2.6))


def band(o, y, title, payloads, labels, sizes, box):
    o.append(mono(title, M, y - 3.0, 3.0))
    x = M
    for size, payload, lbl in zip(sizes, payloads, labels):
        g, n, u = qr_svg(payload, size, x, y, "L")
        o.append(f'<rect x="{x-1.3:.2f}" y="{y-1.3:.2f}" width="{size+2.6:.2f}" '
                 f'height="{size+2.6:.2f}" fill="#fff"/>')
        o.append(g)
        mark = "  ← strip" if abs(size - box) < 0.01 else ""
        o.append(mono(f"{size:g} mm{mark}", x + size / 2, y + size + 4.0, 2.3, anchor="middle"))
        o.append(mono(f"{u:.3f} · {n}mod", x + size / 2, y + size + 7.0, 2.0, "#777", anchor="middle"))
        o.append(mono(lbl, x + size / 2, y + size + 10.0, 2.0, "#777", anchor="middle"))
        x += size + 17.0
    return y + max(sizes) + 16


def variants(url):
    """Payload variants of the user's own URL: shorter or denser encodings may
    give a smaller symbol, but only a scan shows whether they still open."""
    out = [(url, f"as generated, {len(url)} ch")]
    if "://" in url:
        bare = url.split("://", 1)[1]
        out.append((bare, f"no scheme, {len(bare)} ch — opens?"))
    else:
        full = "https://" + url
        out.append((full, f"with https://, {len(full)} ch"))
    if url.upper() != url:
        out.append((url.upper(), f"uppercase, {len(url)} ch — opens?"))
    out.append((PROBE.format(size="STRIP"), "density probe, not a link"))
    return out


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
    except CsvError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    linked = [p for p in parts if p.qr]
    if not linked:
        print("error: no rows with a SKU, so there is nothing to link to", file=sys.stderr)
        return 1
    W = a.feeder or parts[0].feeder
    box = min(W - 2 * QR_PAD, QR_MAX)
    sizes = [round(box + d, 2) for d in OFFSETS if box + d > 3.0]
    urls = [linked[i % len(linked)].qr for i in range(len(sizes))]
    skus = [linked[i % len(linked)].sku for i in range(len(sizes))]
    q = segno.make(urls[0], error="L", micro=False)
    n = q.symbol_size(border=0)[0]

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
         f'viewBox="0 0 {PAGE_W} {PAGE_H}"><rect width="{PAGE_W}" height="{PAGE_H}" fill="#fff"/>']
    o.append(mono(f"QR scan test — {W:g} mm strip", M, 24, 4.2))
    head = [
        "Print at 100%, best quality, on the sticker stock you will use. Scan with your usual phone.",
        f"A {W:g} mm strip holds a {box:g} mm QR box. Your URL is {len(urls[0])} characters: a version "
        f"{q.version} symbol,",
        f"{n} modules, {box / n:.3f} mm per module. Row 1 is that real link at sizes around the strip box.",
        "Row 2 is a DENSITY PROBE, not a link: it shows text when scanned, and tells you what a",
        "shorter payload (e.g. a redirect on your own short domain) would buy.",
    ]
    for i, line in enumerate(head):
        o.append(mono(line, M, 31 + i * 4.2, 2.5, "#444"))
    ruler_y = 31 + len(head) * 4.2 + 3.0
    ruler(o, ruler_y)

    y = band(o, ruler_y + 13, f"1 — the real link ({n} modules, v{q.version})",
             urls, skus, sizes, box)
    y = band(o, y + 6, "2 — DENSITY PROBE, not a link — scanning shows text, not a page",
             [PROBE.format(size=f"{s:g}MM") for s in sizes], ["probe"] * len(sizes), sizes, box)

    o.append(mono(f"3 — payload variants of your URL, all at {box:g} mm", M, y + 3, 3.0))
    yy = y + 8
    x = M
    for payload, lbl in variants(urls[0]):
        g, nn, u = qr_svg(payload, box, x, yy, "L")
        o.append(f'<rect x="{x-1.3:.2f}" y="{yy-1.3:.2f}" width="{box+2.6:.2f}" '
                 f'height="{box+2.6:.2f}" fill="#fff"/>')
        o.append(g)
        o.append(mono(lbl, x, yy + box + 4.0, 2.2))
        o.append(mono(f"{nn} mod · {u:.3f} mm", x, yy + box + 7.0, 2.0, "#777"))
        x += 45.0
    y = yy + box + 14

    o.append(mono(f"4 — real {W:g} mm strips at 1:1", M, y, 3.0))
    o.append(mono("the strip width limits the quiet zone as well as the module size", M, y + 4.0, 2.4, "#444"))
    y += 9
    strips = [p for p in parts if p.feeder == W][:4]
    st = plan(strips, W) if strips else None
    for i, p in enumerate(strips):
        o.append(f'<g transform="translate({M},{y + i * (W + 3)})">{draw_strip(p, st)}'
                 f'<rect width="{STRIP_L}" height="{W}" fill="none" stroke="#bbb" stroke-width="0.12" '
                 f'stroke-dasharray="1 1"/></g>')
        o.append(mono(f"{p.value}  ·  {p.sku}", M + STRIP_L + 4, y + W / 2 + 1 + i * (W + 3), 2.4, "#555"))
    if not strips:
        o.append(mono(f"(no parts with a {W:g} mm feeder in the CSV)", M, y + 4, 2.4, "#777"))
    y += max(1, len(strips)) * (W + 3) + 6

    o.append(mono("Report back: smallest cell in row 1 that OPENS THE PART, and in row 2 that DECODES,",
                  M, y + 4, 2.6))
    o.append(mono("plus which section-3 variants still open the right page.", M, y + 8, 2.5, "#444"))
    ruler(o, min(y + 20, PAGE_H - 22), "50.0 mm — second ruler, in case the first clipped")
    o.append("</svg>")

    a.out.mkdir(parents=True, exist_ok=True)
    out = a.out / f"qr_scan_test_sheet_{W:g}mm_A4.svg"
    out.write_text("".join(o), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
