"""Printable AprilTag sheet for head tracking on the headset (AprilTagCameraSource.cs + HeadMarkerTracker.cs).

Usage:  python tools/make_apriltag_markers.py [output_dir]
Writes  seeg_apriltag_markers.pdf
        page 1: headband set, tags 0 (forehead), 1 (left side), 2 (right side), inner square 40 mm
        page 2: one large tag 3, inner square 55 mm
Family tagStandard41h12 (the only family supported by the jp.keijiro.apriltag Unity package).
TAG SIZE = edge of the INNER square = 5 of the 9 cells (the pose estimation needs exactly this number). The sizes are
set in AprilTagCameraSource (headbandTagMm = 40, largeTagMm = 55); the printer scale (0.95 for the university
printer) in HeadMarkerTracker.printScale. Print at 100 % and check the 100 mm scale bar.
Requires: pip install reportlab
"""
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4

# 9x9 bit patterns (1 = black) of tagStandard41h12 ids 0-3, from github.com/AprilRobotics/apriltag-imgs
TAGS = {
    0: "001000011 111111111 010000011 110000010 110110011 110101010 010000011 111111111 001011011",
    1: "001000010 111111111 010000011 110000011 010100010 010010011 110000011 011111110 101000110",
    2: "001000010 011111110 010000010 110001010 110011010 010100010 110000010 111111110 101010111",
    3: "001000001 011111110 010000010 110111010 010001011 110000010 110000011 011111111 001001110",
}


def draw_tag(c, tag_id, inner_mm, cx, top, label):
    """Draw tag `tag_id` with an inner square of `inner_mm` (5 cells), centred at cx, top edge of the cut frame at
    `top`. A white margin of one cell is kept around the 9x9 tag. Returns the y of the bottom of the label."""
    rows = TAGS[tag_id].split()
    cell = inner_mm / 5.0 * mm
    frame = 11 * cell                                   # 9 cells + 1 white cell on each side
    x0 = cx - frame / 2
    c.setDash(3, 3)
    c.setLineWidth(0.4)
    c.setStrokeGray(0.55)
    c.rect(x0, top - frame, frame, frame, stroke=1, fill=0)
    c.setDash()
    c.setFillGray(0)
    for r, row in enumerate(rows):
        y = top - (2 + r) * cell
        col = 0
        while col < 9:                                  # merge horizontal runs (no hairline gaps)
            if row[col] == "1":
                start = col
                while col < 9 and row[col] == "1":
                    col += 1
                c.rect(x0 + (1 + start) * cell, y, (col - start) * cell, cell, stroke=0, fill=1)
            else:
                col += 1
    bottom = top - frame
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(cx, bottom - 6 * mm, f"AprilTag {tag_id}  -  {label}")
    c.setFont("Helvetica", 8)
    c.drawCentredString(cx, bottom - 10.5 * mm,
                        f"tagStandard41h12, inner square {inner_mm:g} mm (tag size), whole tag {inner_mm * 9 / 5:g} mm")
    return bottom - 10.5 * mm


def scale_bar(c, x, y, length_mm=100):
    c.setLineWidth(0.8)
    c.setStrokeGray(0)
    c.line(x, y, x + length_mm * mm, y)
    c.setFont("Helvetica", 7)
    for i in range(0, length_mm + 1, 10):
        h = 3 * mm if i % 50 == 0 else 1.8 * mm
        c.line(x + i * mm, y, x + i * mm, y + h)
        if i % 50 == 0:
            c.drawCentredString(x + i * mm, y + 4 * mm, f"{i}")
    c.drawString(x + length_mm * mm + 3 * mm, y - 1, "mm")


def header(c, title):
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, PAGE_H - 18 * mm, title)
    c.setFont("Helvetica", 8.5)
    lines = [
        "Print at 100% / 'Actual size' (NOT 'Fit to page'). Check the scale bar: it should measure 100 mm "
        "(university printer: 95 mm -> printScale 0.95).",
        "Glue flat onto stiff cardboard, matte paper preferred. Cut along the dashed line (keep the white border).",
        "The tags must not bend or slide on the head. Do not cover the nasion, the eye corners and the ears "
        "(registration landmarks).",
    ]
    for i, t in enumerate(lines):
        c.drawString(20 * mm, PAGE_H - (25 + 4.5 * i) * mm, t)
    scale_bar(c, 20 * mm, PAGE_H - 46 * mm)


def make(path):
    c = canvas.Canvas(path, pagesize=A4)
    c.setTitle("SEEG head markers - AprilTags")
    header(c, "SEEG headband set - AprilTags 0, 1, 2 (inner square 40 mm)")
    left, right = PAGE_W * 0.29, PAGE_W * 0.71
    b = draw_tag(c, 0, 40, left, PAGE_H - 54 * mm, "front (forehead)")
    draw_tag(c, 1, 40, right, PAGE_H - 54 * mm, "left side (her left)")
    draw_tag(c, 2, 40, PAGE_W / 2, b - 12 * mm, "right side (her right)")
    c.showPage()
    header(c, "SEEG head marker - large AprilTag 3 (inner square 55 mm)")
    draw_tag(c, 3, 55, PAGE_W / 2, PAGE_H - 58 * mm, "large, forehead / clamp")
    c.showPage()
    c.save()


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    make(os.path.join(out, "seeg_apriltag_markers.pdf"))
    print("written to", os.path.abspath(out))
