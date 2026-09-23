"""Print-and-scan diagnostic for the strip QR.

Every code opens a real LCSC product page, and each cell uses a different part,
so whatever your phone lands on names the cell that worked.

Everything sits between y=20 and y=250 so nothing lands in a printer's
unprintable trailing-edge margin.
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from labels import (draw_strip, qr_svg, text, PAGE_W, PAGE_H, MARGIN_X,
                    QR_TEMPLATE, QR_PAD, QR_MAX, load_csv, plan)

M = 15.0
STRIP_BOX = min(8.0 - 2 * QR_PAD, QR_MAX)          # what the 8 mm strip actually holds
SIZES = [6.6, 7.0, STRIP_BOX, 7.8, 8.4, 9.0]
# Row 2 is a DENSITY PROBE, not a link. It measures whether a 21-module symbol
# survives your printer. It deliberately does not pretend to be a URL, because a
# URL on a domain nobody owns is a dead code that teaches you nothing.
PROBE = "PROBE V1 {size} NOT A LINK"
SKU = {
    "a": ["C23138", "C25804", "C21190", "C25744", "C14663", "C1525"],
    "b": ["C19702", "C2286", "C72043", "C72041", "C7519", "C23138"],
}


def mono(s, x, y, size, fill="#111", anchor="start"):
    return text(s, x, y, size, fill, mono=True, anchor=anchor)


def ruler(o, y, label="50.0 mm — if this is not 50 mm, the print was rescaled"):
    o.append(f'<line x1="{M}" y1="{y}" x2="{M + 50}" y2="{y}" stroke="#111" stroke-width="0.3"/>')
    for i in range(6):
        o.append(f'<line x1="{M + i * 10}" y1="{y - 2}" x2="{M + i * 10}" y2="{y}" '
                 f'stroke="#111" stroke-width="0.3"/>')
    o.append(mono(label, M + 53, y, 2.6))


def band(o, y, title, template, skus, ecc="L", probe=False):
    o.append(mono(title, M, y - 3.0, 3.0))
    x = M
    for size, sku in zip(SIZES, skus):
        payload = (template.format(size=f"{size:g}MM") if probe
                   else template.format(sku=sku))
        g, n, u = qr_svg(payload, size, x, y, ecc)
        o.append(f'<rect x="{x-1.3:.2f}" y="{y-1.3:.2f}" width="{size+2.6:.2f}" '
                 f'height="{size+2.6:.2f}" fill="#fff"/>')
        o.append(g)
        mark = "  ← strip" if abs(size - STRIP_BOX) < 0.01 else ""
        o.append(mono(f"{size:g} mm{mark}", x + size / 2, y + size + 4.0, 2.3, anchor="middle"))
        o.append(mono(f"{u:.3f} · {n}mod", x + size / 2, y + size + 7.0, 2.0, "#777", anchor="middle"))
        o.append(mono("probe" if probe else sku, x + size / 2, y + size + 10.0, 2.0,
                      "#777", anchor="middle"))
        x += size + 17.0
    return y + 32


def main():
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
         f'viewBox="0 0 {PAGE_W} {PAGE_H}"><rect width="{PAGE_W}" height="{PAGE_H}" fill="#fff"/>']
    o.append(mono("QR scan test 2 — SMD magazine strip", M, 24, 4.2))
    head = [
        "Print at 100%, and this time try BEST / HIGH quality — it is usually worth one size step.",
        "Last run: 8.4 mm scanned, 7.8 mm did not, 7.2 mm scanned only with effort. That puts your",
        "floor near 0.29 mm per module. The 8 mm strip holds a 7.4 mm box, so the fix is fewer",
        "modules — but the LCSC path is case-sensitive, so it cannot use dense alphanumeric mode. Row 1 is that",
        "URL at 0.255 mm. Row 2 is a DENSITY PROBE, not a link: it shows text when scanned, and",
        "tells you what a short redirect host would buy before you go and register one.",
    ]
    for i, line in enumerate(head):
        o.append(mono(line, M, 31 + i * 4.2, 2.5, "#444"))
    ruler_y = 31 + len(head) * 4.2 + 3.0          # always clear of the header
    ruler(o, ruler_y)

    y = band(o, ruler_y + 13, "1 — the real link: https://lcsc.com/product-detail/SKU.html   (29 modules, v3)",
             QR_TEMPLATE, SKU["a"])
    y = band(o, y + 6, "2 — DENSITY PROBE, not a link — scanning shows text, not a page   (21 modules, v1)",
             PROBE, SKU["b"], probe=True)

    o.append(mono(f"3 — payload length, all at {STRIP_BOX:g} mm (exactly what the 8 mm strip gives)",
                  M, y + 3, 3.0))
    yy = y + 8
    variants = [("https://lcsc.com/product-detail/C14663.html", "the default URL, 43 ch"),
                ("https://www.lcsc.com/product-detail/C14663.html", "with www, 47 ch"),
                ("HTTPS://LCSC.COM/PRODUCT-DETAIL/C14663.HTML", "uppercase — wrong page"),
                ("PROBE V1 7.4MM NOT A LINK", "v1 density probe, not a link")]
    x = M
    for payload, lbl in variants:
        g, n, u = qr_svg(payload, STRIP_BOX, x, yy, "L")
        o.append(f'<rect x="{x-1.3:.2f}" y="{yy-1.3:.2f}" width="{STRIP_BOX+2.6:.2f}" '
                 f'height="{STRIP_BOX+2.6:.2f}" fill="#fff"/>')
        o.append(g)
        o.append(mono(lbl, x, yy + STRIP_BOX + 4.0, 2.3))
        o.append(mono(f"{n} mod · {u:.3f} mm", x, yy + STRIP_BOX + 7.0, 2.0, "#777"))
        x += 45.0
    y = yy + STRIP_BOX + 14

    o.append(mono("4 — real 8 mm strips at 1:1, with the new default payload", M, y, 3.0))
    o.append(mono("the strip width limits the quiet zone as well as the module size", M, y + 4.0, 2.4, "#444"))
    y += 9
    csv_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
    parts = load_csv(csv_path, 8.0, QR_TEMPLATE)[:4] if csv_path else []
    st = plan(parts, 8.0) if parts else None
    for i, p in enumerate(parts):
        o.append(f'<g transform="translate({M},{y + i * 11})">{draw_strip(p, st)}'
                 f'<rect width="37" height="8" fill="none" stroke="#bbb" stroke-width="0.12" '
                 f'stroke-dasharray="1 1"/></g>')
        o.append(mono(f"{p.value}  ·  {p.sku}", M + 41, y + 5.5 + i * 11, 2.4, "#555"))
    y += len(parts) * 11 + 8

    o.append(mono("Report back: smallest cell in row 1 that OPENS THE PART, and in row 2 that DECODES.", M, y + 4, 2.6, "#111"))
    o.append(mono("Row 2 reaching lower than row 1 means a short redirect host would buy you a size step.", M, y + 8, 2.5, "#444"))
    ruler(o, min(y + 20, PAGE_H - 30), "50.0 mm — second ruler, in case the first clipped")
    o.append("</svg>")

    out = pathlib.Path(__file__).parent / "out" / "qr_scan_test_sheet_A4.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text("".join(o), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
