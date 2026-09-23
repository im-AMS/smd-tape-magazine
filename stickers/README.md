# Magazine stickers

Generates two stickers per part from a parts list, laid out on A4 for cutting
with a knife and a ruler.

| sticker | size | face on the magazine | content |
|---|---|---|---|
| front | `W × 11` | small chamfer at the dispensing end | package, value, qualifier |
| strip | `W × 37` | angled top edge | value·package rule, headline, supplier + qty, QR |

`W` is the tape size (8 / 12 / 16 mm). Both lengths are fixed — only the width
tracks the feeder, which is why the two stickers share a column grid and can be
paired one cell per part.

## Run

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install segno fonttools
python labels.py example.csv --out out           # try it on the bundled example
python labels.py "path/to/parts.csv" --out out --pdf
python qr_test.py "path/to/parts.csv"      # print-and-scan diagnostic
python experiment.py "path/to/parts.csv"   # one-sheet design experiment
```

Fonts are bundled in `fonts/` (OFL) and text is converted to outlines, so
nothing needs installing and the PDF renders identically anywhere.

## Options

| flag | effect |
|---|---|
| `--feeder 12` | cartridge width; 8 is the default |
| `--gutter 0.5` | white between stickers; cuts run down its middle |
| `--qr-template` | payload; `{sku}` is substituted. Default is the Robu search URL |
| `--pdf` | also run `inkscape` to produce PDF |

## Experiment sheet

`experiment.py` puts every open design question on a single A4 so they can be
settled in one print rather than a series of them. Each cell is coded so results
can be reported without ambiguity:

| section | codes | question |
|---|---|---|
| 1 | `A1`–`F3` | strip layout: knockout rule, colour bar ×2, colour rail, or rail with no repeat line |
| 2 | `K16`–`K24`, `P`, `T` | reverse type vs positive vs dark-on-tint, 1.6–2.4 mm |
| 3 | `V24`–`V36`, `P20`–`P26` | front sticker value size and package size |
| 4 | `D17L`–`D20D` | detail line: size and grey vs dark |
| 5 | — | do the eight class colours stay distinct on your stock |
| 6 | `G02`, `G03`, `G05` | gutter width — cut all three and see |

Sections 1, 3 and 6 carry light grey corner crop marks so real stickers can be
cut out of the experiment sheet for practice. The marks are `#B9C0BD`, light
enough to cut straight through without leaving a visible edge — cut guides
belong outside the artwork, and never in black next to it.

Reverse type is the hard case: ink spreads into white strokes and thins them, so
white-on-colour fails at a larger size than black-on-white. Section 2 finds where.

## Type — settled by print test

Sizes are not theoretical; they were chosen off a printed experiment sheet
(glossy sticker stock, MP tray, best quality) and are fixed constants in
`labels.py`. Strings that will not fit are demoted individually by `_fit_step`
rather than shrinking every sticker on the sheet.

| what | size | experiment code |
|---|---|---|
| front value | 3.2 mm | V32 |
| front package | 2.6 mm | P26 |
| front qualifier | 2.3 mm | — |
| strip line 1 (repeat) | 2.15 mm | layout B |
| strip line 2 (spec) | 2.6 mm | layout B |
| strip detail | 1.85 mm light grey | D18L, floor D17L |

**Strip layout B**: a plain colour bar with every character on white. Line 1
repeats the front sticker so it is demoted and greyed; line 2 is the spec, the
only thing the strip says that the front sticker does not.

Reverse type tested fine on glossy stock, which is why the front sticker's
package band is still white on solid colour. On plain paper it was the weakest
element on the sheet — the stock, not the design, was the problem.

## Cutting and bleed

`--gutter` (default 0.25 mm) sets the gap between stickers and the cut runs down
its middle, so every boundary is still a single straight full-sheet cut.

The gap is **not white**. Each sticker's edge colour is extended by half the
gutter, so the two bleeds meet exactly on the cut line. A cut that drifts then
shows colour rather than a white sliver, which is what reads as a printing
fault. Because the parts list is grouped by class, most neighbours share a
colour and most cut lines are invisible; only a class change leaves a two-colour
seam, and drifting there picks up the neighbour's hue rather than white.

The QR needs no special handling. Nothing coloured is allowed within 0.8 mm of
it, so its bleed is white — which is exactly what a quiet zone is. The 0.3 mm
quiet zone at the trim line only grows if the cut drifts outward. Long ticks mark cell edges, short ticks the split between a
part's front sticker and its strip.

## Input

Columns are read **by position**, because the Robu export repeats `kind`:

```
kind, value, tolerance, rating, subtype, footprint, sku, quantity
```

`kind` maps to a class (R C L D Q U J X) which picks the colour and decides the
strip headline: passives lead with their spec, semiconductors lead with the part
number. Values are normalised on the way in — `100n` → `100nF`, `330` → `330R`.

## Printing

Print at 100%. Every sheet carries a 50 mm calibration bar — measure it before
committing sticker paper, because "fit to page" is the usual way to waste one.

Cut ticks sit in the margins, never on a sticker. Long ticks are cell edges,
short ticks the split between a part's front sticker and its strip.

## QR

Payload length decides the symbol version, version decides the module count, and
module count decides whether it survives printing. The strip width is a hard
ceiling on the box, because a QR is square and cannot use the 37 mm length.

Measured on an inkjet, normal quality, plain paper, iOS camera:

| module size | result |
|---|---|
| 0.336 mm (8.4 mm box, 29 mod) | scanned |
| 0.269 mm (7.8 mm box, 29 mod) | did not scan |
| 0.248 mm (7.2 mm box, 29 mod) | scanned only with effort |

Working floor is roughly **0.29 mm per module**. An 8 mm strip gives a 7.4 mm
box, and the Robu URL is 44 bytes, which is a version 3 symbol: **0.255 mm**.
That is below the floor at normal quality; best/high quality may clear it.

**The URL cannot be shortened.** Robu's search only returns the product with
`post_type=product`, and version 2 holds 32 bytes at ECC L. Dropping the scheme
gets to 35, still too long. Uppercasing does not help because `?`, `=` and `&`
are outside QR alphanumeric mode — that trick only works on path-style URLs.

### If 0.255 mm will not scan

The one remaining lever is a short redirect on a host you own. A path-style URL
in uppercase stays in alphanumeric mode and holds version 1:

| payload | chars | version | mm/module @ 7.4 |
|---|---|---|---|
| `https://robu.in/?s=SKU&post_type=product` | 44 | 3 | 0.255 |
| `HTTP://AMS.SH/R178998` | 21 | 1 | **0.352** |

That is a 38% larger module in the same box — comfortably past your floor.

A Cloudflare Worker is enough:

```js
export default {
  fetch(request) {
    const sku = new URL(request.url).pathname.slice(1).toUpperCase();
    if (!sku) return new Response("no sku", { status: 404 });
    return Response.redirect(
      `https://robu.in/?s=${sku}&post_type=product`, 301);
  },
};
```

Point a short domain at it, then generate with:

```sh
python labels.py parts.csv --qr-template "HTTP://AMS.SH/{sku}"
```

Uppercase in the template is deliberate and required — one lowercase character
drops the payload into byte mode and costs you the version 1 symbol. Scheme and
host are case-insensitive so the link still resolves. Verify that your scanner
linkifies the uppercase form before committing a sheet.

## Printing

Print at 100%, best/high quality. Every sheet carries a 50 mm calibration bar —
measure it before committing sticker paper.

Content is kept 20 mm clear of the trailing edge (`MARGIN_Y`, `FOOTER_Y`),
because that is the margin inkjets clip.
