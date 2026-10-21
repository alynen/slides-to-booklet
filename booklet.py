"""Turn a slide deck PDF into a portrait note-taking booklet.

US Letter portrait: a dark cover with the title slide, then pages with
2 slides stacked, 3 note lines under each slide, and a gradient band
with the page number (even numbers left, odd right).

Usage:
    python3 booklet.py deck.pdf "Deck Booklet.pdf" [COVER]

COVER is the 0-based index of the title slide (default 0). Slides
before it are left out, which helps when slide 1 is only a logo.

Requires: pip install pypdf reportlab
"""
import io
import sys

from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

# ---------- style (change these to match your brand) ----------
PAGE_BG = (226, 223, 222)       # light gray content pages
COVER_BG = (19, 16, 14)         # dark cover
NOTE_LINE = (200, 197, 195)     # note lines
BAND = [(40, 101, 129), (53, 173, 117), (90, 198, 167)]  # footer gradient, left to right

# ---------- layout (points, US Letter) ----------
W, H = 612, 792
X0, SW = 45, 522                # slide left edge and width
TOPS = [34, 382]                # top of each slide slot
NOTE_H = 46                     # note area under each slide
FOOT = 40                       # footer band height


def rgb(c):
    return Color(*(v / 255 for v in c))


def background(reader_page_size, num, slots=2, cover=False):
    """Draw one page background and return it as a pypdf page."""
    _, sh = reader_page_size
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    if cover:
        c.setFillColor(rgb(COVER_BG))
        c.rect(0, 0, W, H, stroke=0, fill=1)
    else:
        c.setFillColor(rgb(PAGE_BG))
        c.rect(0, 0, W, H, stroke=0, fill=1)
        # note area only under slots that hold a slide
        for top in TOPS[:slots]:
            y = H - top - sh
            c.setFillColor(Color(1, 1, 1))
            c.rect(X0, y - NOTE_H, SW, NOTE_H, stroke=0, fill=1)
            c.setStrokeColor(rgb(NOTE_LINE))
            c.setLineWidth(0.6)
            for i in range(1, 4):
                ly = y - NOTE_H * i / 4 + 1
                c.line(X0 + 10, ly, X0 + SW - 10, ly)
        # gradient footer band
        steps = 60
        for i in range(steps):
            t = i / (steps - 1)
            a, b = (BAND[0], BAND[1]) if t < 0.5 else (BAND[1], BAND[2])
            u = t * 2 if t < 0.5 else t * 2 - 1
            c.setFillColor(Color(*[(a[k] + (b[k] - a[k]) * u) / 255 for k in range(3)]))
            c.rect(W * i / steps, 0, W / steps + 1, FOOT, stroke=0, fill=1)
        c.setFillColor(Color(1, 1, 1))
        c.setFont("Helvetica-Bold", 11)
        if num % 2 == 0:
            c.drawString(X0, FOOT / 2 - 4, str(num))
        else:
            c.drawRightString(X0 + SW, FOOT / 2 - 4, str(num))
    c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def build(src, out, cover_index=0):
    r = PdfReader(src)
    box = r.pages[0].mediabox
    sw, sh = float(box.width), float(box.height)
    scale = SW / sw
    slot_h = sh * scale

    w = PdfWriter()

    # cover: title slide full width, centered on dark
    cover = background((SW, slot_h), 0, cover=True)
    cs = W / sw
    cover.merge_transformed_page(
        r.pages[cover_index],
        Transformation().scale(cs).translate(0, (H - sh * cs) / 2),
    )
    w.add_page(cover)

    # content: 2 slides per page
    rest = list(range(cover_index + 1, len(r.pages)))
    num = 1
    for i in range(0, len(rest), 2):
        chunk = rest[i:i + 2]
        page = background((SW, slot_h), num, slots=len(chunk))
        for idx, top in zip(chunk, TOPS):
            page.merge_transformed_page(
                r.pages[idx],
                Transformation().scale(scale).translate(X0, H - top - slot_h),
            )
        w.add_page(page)
        num += 1

    # dedupe repeated slide resources (logos, backgrounds) to keep the file small
    try:
        w.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    except TypeError:  # older pypdf
        w.compress_identical_objects(remove_identicals=True, remove_orphans=True)

    with open(out, "wb") as f:
        w.write(f)
    return len(w.pages)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    pages = build(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0)
    print(f"{pages} pages written to {sys.argv[2]}")
