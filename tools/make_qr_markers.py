"""Printable QR marker sheets for head tracking on the headset (HeadMarkerTracker.cs).

Usage:  python tools/make_qr_markers.py [output_dir]
Writes  seeg_qr_markers.pdf        (SEEG-HEAD-1 100 mm, SEEG-HEAD-2/3 70 mm)
        seeg_qr_markers_small.pdf  (size test 60/50/40/30 mm + headband set 3 x 50 mm)
Payload convention: SEEG-HEAD-<n>[-<size>MM]. Print at 100 % and check the 100 mm scale bar;
the university printer gives 95 mm -> HeadMarkerTracker.printScale = 0.95.
Requires: pip install segno reportlab
"""
import segno
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4
QUIET = 4  # quiet zone in modules (QR spec minimum)


def draw_qr(c, payload, size_mm, cx, top):
    """Draw a QR code whose symbol (without quiet zone) is size_mm wide, centred at cx.
    Returns the y coordinate of the bottom of the cut frame."""
    qr = segno.make_qr(payload, version=1)
    matrix = [list(row) for row in qr.matrix]
    n = len(matrix)
    mod = size_mm * mm / n
    frame = (n + 2 * QUIET) * mod
    x0 = cx - frame / 2
    y_top = top
    # dashed cut frame (outside the quiet zone)
    c.setDash(3, 3)
    c.setLineWidth(0.4)
    c.setStrokeGray(0.5)
    c.rect(x0, y_top - frame, frame, frame, stroke=1, fill=0)
    c.setDash()
    # modules, merged into horizontal runs to avoid hairline gaps
    c.setFillGray(0)
    for r, row in enumerate(matrix):
        y = y_top - (QUIET + r + 1) * mod
        col = 0
        while col < n:
            if row[col]:
                start = col
                while col < n and row[col]:
                    col += 1
                c.rect(x0 + (QUIET + start) * mod, y, (col - start) * mod, mod,
                       stroke=0, fill=1)
            else:
                col += 1
    bottom = y_top - frame
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(cx, bottom - 6 * mm, payload)
    c.setFont("Helvetica", 8)
    c.drawCentredString(
        cx, bottom - 10.5 * mm,
        f"symbol {size_mm} x {size_mm} mm, {n}x{n} modules, "
        f"EC {qr.error.upper()}, keep white border")
    return bottom


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
        "Print at 100% / 'Actual size' (NOT 'Fit to page'). Check the scale bar: it must measure exactly 100 mm.",
        "Glue flat onto stiff cardboard, matte paper preferred (glossy paper reflects light). Cut along the dashed line.",
        "Do not cover the white border, do not bend the marker. Measure the printed symbol and enter the real size in the app.",
    ]
    for i, t in enumerate(lines):
        c.drawString(20 * mm, PAGE_H - (25 + 4.5 * i) * mm, t)
    scale_bar(c, 20 * mm, PAGE_H - 46 * mm)


def large(path):
    c = canvas.Canvas(path, pagesize=A4)
    c.setTitle("SEEG head marker - QR codes")
    header(c, "SEEG head marker - main QR code (100 mm)")
    draw_qr(c, "SEEG-HEAD-1", 100, PAGE_W / 2, PAGE_H - 62 * mm)
    c.showPage()
    header(c, "SEEG head markers - extra QR codes (70 mm)")
    b = draw_qr(c, "SEEG-HEAD-2", 70, PAGE_W / 2, PAGE_H - 54 * mm)
    draw_qr(c, "SEEG-HEAD-3", 70, PAGE_W / 2, b - 16 * mm)
    c.showPage()
    c.save()


def small(path):
    c = canvas.Canvas(path, pagesize=A4)
    c.setTitle("SEEG head marker - small QR codes")
    header(c, "SEEG QR size test (60 / 50 / 40 / 30 mm)")
    L, R = PAGE_W * 0.29, PAGE_W * 0.71
    b1 = draw_qr(c, "SEEG-TEST-60MM", 60, L, PAGE_H - 54 * mm)
    draw_qr(c, "SEEG-TEST-50MM", 50, R, PAGE_H - 54 * mm)
    draw_qr(c, "SEEG-TEST-40MM", 40, L, b1 - 22 * mm)
    draw_qr(c, "SEEG-TEST-30MM", 30, R, b1 - 22 * mm)
    c.showPage()
    header(c, "SEEG headband set - 3 x QR 50 mm")
    b = draw_qr(c, "SEEG-HEAD-1-50MM", 50, L, PAGE_H - 54 * mm)
    draw_qr(c, "SEEG-HEAD-2-50MM", 50, R, PAGE_H - 54 * mm)
    draw_qr(c, "SEEG-HEAD-3-50MM", 50, PAGE_W / 2, b - 22 * mm)
    c.showPage()
    c.save()


if __name__ == "__main__":
    import os
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    large(os.path.join(out, "seeg_qr_markers.pdf"))
    small(os.path.join(out, "seeg_qr_markers_small.pdf"))
    print("written to", os.path.abspath(out))
