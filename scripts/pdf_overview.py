"""Contact sheet of selected pages of a PDF (visual review aid).

  python scripts/pdf_overview.py FILE.pdf OUT.png [pages e.g. 1,2,3,-1]
"""
import sys

import pymupdf

doc = pymupdf.open(sys.argv[1])
pages = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else list(range(1, min(doc.page_count, 6) + 1))
pages = [p if p > 0 else doc.page_count + 1 + p for p in pages]
w, h = doc[0].rect.width, doc[0].rect.height
cols = min(len(pages), 3)
rows = (len(pages) + cols - 1) // cols
sheet = pymupdf.open()
pg = sheet.new_page(width=cols * (w + 10), height=rows * (h + 24))
for n, p in enumerate(pages):
    x, y = (n % cols) * (w + 10), (n // cols) * (h + 24)
    r = pymupdf.Rect(x, y + 18, x + w, y + 18 + h)
    pg.show_pdf_page(r, doc, p - 1)
    pg.draw_rect(r, color=(0.5, 0.5, 0.5), width=0.7)
    pg.insert_text((x + 4, y + 13), f"page {p} of {doc.page_count}", fontsize=11, color=(1, 0, 0))
pg.get_pixmap(dpi=int(sys.argv[4]) if len(sys.argv) > 4 else 60).save(sys.argv[2])
