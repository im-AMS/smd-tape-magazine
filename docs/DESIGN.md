# Design notes

How the FreeCAD model is built, and the traps found while building it. Read
this before editing anything beyond the `Parameters` sheet.

The geometry started from the STL of
[SMD Component Tape Magazine (8, 12, 16mm)](https://www.printables.com/model/580643)
by Lord Asdi. That model is STL only, so the outline was traced from the mesh
and everything else was rebuilt as a driven model. The traced outline is now
plain sketch geometry; the mesh is no longer in the file.

FreeCAD 1.1.3.

## Files

| path | what |
|---|---|
| `cad/smd-tape-magazine.FCStd` | **the main file**. Holds the `Magazine`, `Lid` and `Slider` bodies and the `Parameters` sheet |
| `cad/latch-socket-cutter.FCStd` | the socket cutter. One solid, used 8× to cut the latch sockets |
| `cad/latch-peg.FCStd` | the peg. One solid, used 8× on the lid |

**Keep the three `.FCStd` files together in `cad/`.** `smd-tape-magazine.FCStd` links to
`latch-socket-cutter.FCStd` and `latch-peg.FCStd` by relative path. Moving all three
together is fine; separating them breaks the binders.

## Object names vs labels

FreeCAD can't rename an object's internal name, only its label (what the tree
shows). Expressions use internal names, and so does this document. Lookup:

| internal name | label in the tree | what it does |
|---|---|---|
| `Body001` | Magazine | the magazine body |
| `Sketch001` / `Pad` | OutlineSketch / Blank | full-thickness slab from the side outline |
| `Sketch002` / `Pocket` | ReelCavitySketch / ReelCavity | hollows the body, leaving the `wall` front web |
| `Sketch003` / `Pocket001` | TopRightRecessSketch / TopRightRecess | 1.2 mm recess at the top-right of the back face |
| `Sketch004` / `Pocket002` | SpringSeatSketch / SpringSeat | seat for the lower end of the slider spring |
| `Chamfer`, `Fillet`…`Fillet003`, `Chamfer003` | TopRightRecessChamfer, RightEdgeFillet, TopEdgeFillet, TopRightRecessFillet, TopRightCornerFillet, LeftCornerChamfer | edge breaks |
| `SocketCut` / `Plug1..8` | LatchSockets / SocketCutter1..8 | cuts the 8 lid sockets |
| `JointPlacement` | LatchPositions | where the 8 latches sit |
| `Chamfer004` | MagazineFirstLayerChamfer | 0.3 mm elephant's-foot chamfer on the bed face |
| `Body002` | Lid | the lid |
| `BodyRef` | LidMagazineRef | binder of the magazine (reference only) |
| `Sketch006` / `Pad001` | LidOutline / LidPlate | the lid plate |
| `PegFuse` / `Peg1..8` | LatchPegs / LatchPeg1..8 | fuses the 8 snap pegs |
| `Chamfer005` | LidFirstLayerChamfer | elephant's-foot chamfer |
| `Body003` | Slider | the slider |
| `SliderRef` | SliderMagazineRef | binder of the magazine; `Sketch007` attaches to it |
| `Sketch007` / `Pad002` | SliderProfile / SliderBlank | slider body |
| `Sketch008` / `Pad003`, `Sketch009` / `Pad004` | BackGuideRib…, FrontGuideRib… | the ribs on each side |
| `Sketch010` / `Pocket003` | SpringBoreSketch / SpringBore | spring bore, depth `spring_pocket` |
| `Chamfer001`, `Chamfer002` | SliderTopChamfer, SliderTopEdgeBreak | top of the slider |
| `Chamfer006` | SliderFirstLayerChamfer | elephant's-foot chamfer |
| `Params` | Parameters | the spreadsheet |

## Parameters

All in `smd-tape-magazine.FCStd` → `Parameters` (internal name `Params`). The sheet is split into colour-coded sections
(FreeCAD spreadsheets have no read-only cells, so this is by convention):

| section | alias | value | drives |
|---|---|---|---|
| **User inputs** (green) | `tape_size` | 8 | SMD tape width — 8 / 12 / 16 |
| | `clearance` | 1 | tape channel clearance |
| | `wall` | 1.2 | body front web, lid plate, slider peg pads |
| | `spring_pocket` | 8 | slider spring bore (original design uses 5; longer springs here) |
| **Fit tuning** (yellow) | `peg_gap` | 0.4 | peg clearance off the flat mating face |
| **Derived** (grey) | `thickness` | `=tape_size + clearance + wall` | |
| | `peg_center_y` | `=(5.12 - 4.71) / 2` | centres the peg across the mating edge |
| **Internal** (grey) | `joint_marker_len` | 2 | length of the `JointPlacement` construction lines (cosmetic) |

**Don't move aliased cells by clearing and re-setting the alias.** Clearing an
alias silently rewrites every expression that used it to the raw cell address
(`Params.joint_marker_len` → `Params.B8`). Undoing that leaves the alias
property unregistered and downstream features go Invalid.

Verified working across `tape_size` 8/12/16 — thickness tracks, sockets and
pegs follow the back face, all bodies stay valid single solids.

**After editing a spreadsheet cell, force a recompute** (right-click the
document → Mark to recompute → refresh). Values do not propagate reliably on
their own, and edits silently queue up and land together later.

## How it's put together

```
Body001 (magazine)          lid (Body002)              slider (Body003)
  Pad          <- thickness   BodyRef   -> Body001       SliderRef -> Body001
  Pocket       <- wall        Sketch006 + Pad001 <- wall Pad002 <- tape_size + clearance/2
  ...                         PegFuse (8 pegs)           Pad003/Pad004 <- wall
  SocketCut (8 sockets)                                  Pocket003 <- spring_pocket
  JointPlacement
```

### Joint placement is sketch-driven

`JointPlacement` (in `Body001`) holds **8 construction lines** — start point is
the joint origin, direction is the mating edge. Both the socket and its lid peg
read from it:

```
Plug<n>.Base.x/.z = JointPlacement.Geometry[n-1].StartPoint.x/.y
Peg<n>.Base.x/.z  = same + peg_gap and peg_center_y offsets
```

So moving a joint moves the socket **and** its peg together — they cannot drift
apart. Dimensioned as position (X, Y) + length (parameter) + angle, so moving a
joint is two numbers:

| joint | constraints (X, Y) | joint | constraints (X, Y) |
|---|---|---|---|
| 1 | `[0]`, `[1]` | 5 | `[16]`, `[17]` |
| 2 | `[4]`, `[5]` | 6 | `[20]`, `[21]` |
| 3 | `[8]`, `[9]` | 7 | `[24]`, `[25]` |
| 4 | `[12]`, `[13]` | 8 | `[28]`, `[29]` |

### Cross-body references use SubShapeBinders

`BodyRef`, `SliderRef`, `Plug1..8`, `Peg1..8` are all
`PartDesign::SubShapeBinder`, `BindMode = Synchronized`. Edit `latch-socket-cutter` and
all 8 sockets update; edit `latch-peg` and all 8 pegs update.

Dependency flows one way: `smd-tape-magazine → latch-socket-cutter / latch-peg`.

## Key measured dimensions

Recovered from the original STL:

- thickness = tape width + 2.000; the 8/12/16 bodies share an identical XZ profile
- hub bore r = 7.500 @ (0.40264, 32.50537)
- reel recess r = 30.000, same centre, 8.800 deep
- three radial slots, w = 2.000, r = 1.000, at exactly 90° / 210° / 330°
- **8** lid snap sockets: mouth 3.4292 at the back face → 11.73° lead-in →
  crest 2.3500 → **65.22° retaining undercut** → cavity 3.6500 to the floor
- socket cutter 5.12 long; peg 4.71 → 0.41 slack, split evenly by `peg_center_y`

## Traps worth remembering

**Never let a mesh become a Body's `BaseFeature`.** A mesh-derived solid is
invalid (the original had 3728 triangle faces); PartDesign features that fuse
against it can come out **empty**, with no error. The pad preview looks fine
because it doesn't run the fuse. Until 2026-09-23 `Body001` still had the
refined STL solid as its BaseFeature, with `Sketch001`/`002`/`005` projecting
~74 edges from it. Those projections were frozen into plain sketch geometry (and the unused `Sketch005` deleted)
and the whole mesh chain was deleted. The body is identical at 8/12/16
(symmetric difference 0 mm³), and the file shrank from 4.7 MB to 0.8 MB.

**Deleting a BaseFeature invalidates edge names downstream.** FreeCAD's
topological names include the history, so after the delete `Fillet` pointed at
an edge name that no longer existed. The recompute stopped there, silently
leaving everything after it at the old size. Each dress-up feature had to be
re-pointed. The indices happened to come out the same, but only the stale
hash was wrong. Always re-run a full 8→12→16 check after structural edits and
confirm the thickness actually changed.

**Coplanar faces break booleans.** Cutters landing exactly on a face fail
non-deterministically — 3 of 8 sockets came out as sealed internal voids, and 3
of 8 pegs refused to fuse. Fix is a 0.05 mm overshoot, baked into the
`Plug`/`Peg` Y expressions. Check `len(Shape.Shells) == 1` — sealed voids report
`valid=True` and give no error.

**`Pocket` with `UpToFace` silently fails below ~0.25 mm offset.** Reports
`Up-to-date` and `valid=True` while keeping the *previous* geometry.

**Don't leave a loose sketch next to a PartDesign Boolean.** A tree edit can
pull it into the Boolean's tool group, which invalidates it and silently drops
the tip. Symptom: body volume jumps ~855 mm³ and the sockets stop being cut.
Check `SocketCut.Group` holds only the 8 binders.

**Sketches attached to binder geometry are fragile.** `lid/Sketch006` used to
be attached to `BodyRef.Face122`, with its lid outline projected from ~28
`BodyRef` edges. Adding `Chamfer003`/`Chamfer004` to the body renamed those
edges, and every recompute then logged "External geometry … missing
reference" for the whole outline (the red errors after a `tape_size` change).
Fixed 2026-09-23: the outline is now the sketch's own geometry (Block-constrained,
identical edges), and the sketch is unattached with
`Placement.Base.y = -Params.thickness`. The trade-off is that **the lid outline
no longer follows edits to the body outline.** Change `Body001/Sketch001`'s
outline and you must update `Sketch006` to match.

**Chamfers and fillets on the body reference edges by name.** Verified at
8/12/16 that they all land on the same geometric edges. Re-check after adding
any feature upstream of them. `Chamfer003` had `Edge199` (a tangent edge that
FreeCAD always skipped) removed; the result is unchanged.

## Latch fit — current understanding

Printed tabs were hard to insert and some broke. Measured causes:

1. **Zero clearance on the flat mating face** — 5.2 mm of zero-gap sliding
   contact. Addressed by `peg_gap = 0.4`.
2. **0.374 mm of forced compression** — the barb crest (2.724) must pass the
   socket constriction (2.350) with nowhere to flex.
3. **Square leading tip** at 90°, no chamfer, so the barb hits the female taper
   as a sharp corner.

Moving the peg does **not** fix (2): it gains room to deflect but pushes the
barb the same distance further in, so net compression stays 0.374. Only widening
the female relieves it. This was studied in a separate overlay file that is not
part of this repo.

The 65.0° barb ramp and 65.3° female undercut are a matched **retention** pair.
Leave them alone; softening them trades insertion force for a lid that pops off.

## Socket wall thickness

Measured at mid-socket depth, thinnest wall per joint:

| joint | wall | perimeters @ 0.4 mm |
|---|---|---|
| 1 | 1.199 | 3.00 |
| 2 | 1.592 | 3.98 |
| 3 | 1.977 | 4.94 |
| 4 | 2.723 | 6.81 |
| 5 | 1.205 | 3.01 |
| 6 | 1.199 | 3.00 |
| 7 | 1.609 | 4.02 |
| 8 | 1.968 | 4.92 |

Aim for whole multiples of the extrusion width. A wall of e.g. 1.344 is 3.36
perimeters — the 0.36 remainder becomes gap-fill, which is a common stringing
source. Joints 1, 5, 6 were nudged onto 1.200 (exactly 3) for this reason.

Note the female relief above would **subtract** from these.

## Open items

- [ ] Female relief not applied. `latch-socket-cutter.FCStd` is untouched; the relief
      was only studied
- [ ] `latch-socket-cutter` and `latch-peg` pad lengths (5.12 / 4.71) are plain values,
      not linked to `peg_center_y`. Change one and update the formula by hand
- [ ] `slider/Sketch009` has zero geometry yet drives `Pad004`. Worth checking
- [ ] Sketches `Sketch002`–`004`, `Sketch007`–`010` are still attached to faces
      by name (`Face59`, `Face72`, …). They hold at 8/12/16 but are the next
      thing to break if features are added upstream
