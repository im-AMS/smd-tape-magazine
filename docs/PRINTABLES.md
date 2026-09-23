# Printables listing (copy-paste)

**Name:** SMD Tape Magazine 8/12/16mm: Parametric (FreeCAD) + Sticker Generator

**Remix of:** https://www.printables.com/model/580643 (SMD Component Tape Magazine by Lord Asdi)

**Category:** Hobby & Makers > Electronics

**Tags:** smd, smt, electronics, organizer, organization, smdcomponents, parametric, freecad, labels

**License:** Creative Commons, Attribution-NonCommercial-ShareAlike 4.0

**Files to upload:** everything in `print/`, plus `cad/*.FCStd` (all three together)

**Images:** `images/assembled.png`, `images/inside.png`, plus photos of real prints

---

## Summary

Parametric SMD tape magazine for 8, 12 and 16 mm tape. Free FreeCAD source
included, plus a sticker generator for matching labels.

## Description

A rebuilt, fully parametric version of the SMD tape magazine. The free
FreeCAD source is included, so you can change the tape width, wall thickness,
channel clearance, spring bore and lid fit from a single colour-coded
spreadsheet.

**What's included**
- Print-ready STLs: body and slider for 8 / 12 / 16 mm, and one lid that fits
  all three
- The parametric FreeCAD model (FreeCAD 1.1+)
- A sticker generator: front + top labels per part with value, package and
  QR code, laid out on A4

**Print in PETG only.** The lid snaps on with eight small pegs; PLA is too
brittle for them.

**Print settings** (0.4 mm nozzle): 0.25 mm layers, 2 walls, 4 top / 3 bottom
layers, 0% infill, no supports. The STLs are pre-oriented with the chamfered
face down.

**Per magazine:** 1 body, 1 slider of the same width, 1 lid, 1 spring. The
spring bore is 8 mm deep, for a longer spring than the original's 0.3 × 4 ×
20 mm. Set `spring_pocket` to 5 in the model to use that one instead.

**Customising:** open `smd-tape-magazine.FCStd` (keep the three .FCStd files
in one folder), double-click `Parameters`, change the green cells, press
Ctrl+R, and export the `Magazine`, `Lid` and `Slider` bodies.

**Source & sticker generator:** <GitHub link>

**Credits**
- Based on *SMD Component Tape Magazine (8, 12, 16mm)* by **Lord Asdi**
  (CC BY 4.0). The outline was traced from it and the model rebuilt as a
  parametric design with reworked latches, sockets and slider.
- Inspired by **robin7331**'s Gen 2 SMD magazine. His original *SMD Component
  Magazines* is the design Lord Asdi's version builds on. Gen 2 hasn't been
  released as open source; this is an open, parametric take on the idea.
