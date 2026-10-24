"""Tile PNGs into contact sheets with pymupdf (no extra dependency). Usage: contact_sheet.py <out.png> <cols> <img>..."""
import sys
import pymupdf

out, cols, imgs = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
W, H = 470, 610
rows = (len(imgs) + cols - 1) // cols
doc = pymupdf.open()
page = doc.new_page(width=cols * W, height=rows * (H + 16))
for i, f in enumerate(imgs):
    x, y = (i % cols) * W, (i // cols) * (H + 16)
    page.insert_text((x + 6, y + 12), f.split("/")[-1], fontsize=10)
    page.insert_image(pymupdf.Rect(x + 4, y + 16, x + W - 4, y + 16 + H), filename=f, keep_proportion=True)
page.get_pixmap(dpi=72).save(out)
