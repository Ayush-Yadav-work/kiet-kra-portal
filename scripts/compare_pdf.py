"""Side-by-side PNG of a source template PDF and a generated PDF, page by page (visual review aid).

  python scripts/compare_pdf.py SOURCE.pdf GENERATED.pdf OUT_PREFIX [dpi]
"""
import sys

import pymupdf

src, gen, out = pymupdf.open(sys.argv[1]), pymupdf.open(sys.argv[2]), sys.argv[3]
dpi = int(sys.argv[4]) if len(sys.argv) > 4 else 70
print(f"source pages={src.page_count} {src[0].rect}, generated pages={gen.page_count} {gen[0].rect}")
for i in range(max(src.page_count, gen.page_count)):
    sheet = pymupdf.open()
    w = max(d[0].rect.width for d in (src, gen))
    h = max(d[0].rect.height for d in (src, gen))
    pg = sheet.new_page(width=2 * w + 20, height=h + 20)
    for j, d in enumerate((src, gen)):
        if i < d.page_count:
            r = pymupdf.Rect(j * (w + 20), 20, j * (w + 20) + d[i].rect.width, 20 + d[i].rect.height)
            pg.show_pdf_page(r, d, i)
            pg.draw_rect(r, color=(0.5, 0.5, 0.5), width=0.5)
        pg.insert_text((j * (w + 20) + 4, 14), ("SOURCE" if j == 0 else "GENERATED") + f" p{i + 1}", fontsize=10,
                       color=(1, 0, 0))
    pg.get_pixmap(dpi=dpi).save(f"{out}_p{i + 1}.png")
