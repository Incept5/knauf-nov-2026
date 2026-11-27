"""Draw a model's chart-data answer (intro, Markdown table, total, optional closing paragraph) as a
chat-style panel for the Day 2 chart slide.
  python3 render_answer_munich.py answer.md out.png [--with-comment]"""
import re, sys
from PIL import Image, ImageDraw, ImageFont
src, out = sys.argv[1], sys.argv[2]
WITH_COMMENT = "--with-comment" in sys.argv[3:]
lines = [l.rstrip() for l in open(src, encoding="utf-8")]
intro = lines[0]
rows = [[c.strip() for c in l.strip("|").split("|")] for l in lines if l.startswith("|") and not re.match(r"^\|\s*-", l)]
total = next(l for l in lines if l.lower().startswith("range"))
comment = " ".join(l for l in lines[lines.index(total) + 1:] if l.strip()) if WITH_COMMENT else ""
S = 2  # draw at 2x
F = lambda sz, b=False: ImageFont.truetype("/System/Library/Fonts/SFNS.ttf" if not b else "/System/Library/Fonts/SFNS.ttf", sz * S)
reg, bold, mono = F(15), F(15), ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 13 * S)
W, pad, rowh = 840 * S, 14 * S, 34 * S
cols = [230 * S, 370 * S, 240 * S]
def wrap(text, font, width):
    out, line = [], ""
    for w in text.split():
        t = (line + " " + w).strip()
        if font.getlength(t) <= width:
            line = t
        else:
            out.append(line); line = w
    return out + ([line] if line else [])
clines = wrap(comment, reg, W - 2 * pad) if comment else []
H = pad + 30 * S + rowh * len(rows) + 16 * S + 28 * S + len(clines) * 24 * S + (8 * S if clines else 0) + pad
im = Image.new("RGB", (W, H), "#F2F2F4"); d = ImageDraw.Draw(im)
y = pad; d.text((pad, y), intro, font=reg, fill="#1A1A1A"); y += 30 * S
x0 = pad
for r, row in enumerate(rows):
    if r == 0:
        d.rectangle([x0, y, x0 + sum(cols), y + rowh], fill="#E4E4E8")
    d.line([x0, y + rowh, x0 + sum(cols), y + rowh], fill="#D0D0D6", width=S)
    x = x0
    for c, cell in enumerate(row):
        ty = y + (rowh - 15 * S) // 2 - 2 * S
        if r > 0 and c == 2 and re.match(r"#[0-9A-Fa-f]{6}", cell):
            d.rectangle([x + 10 * S, ty + 2 * S, x + 26 * S, ty + 18 * S], fill=cell, outline="#888")
            d.text((x + 34 * S, ty + 1 * S), cell, font=mono, fill="#333")
        else:
            d.text((x + 10 * S, ty), cell, font=bold if r == 0 else reg, fill="#1A1A1A")
        x += cols[c]
    y += rowh
d.rectangle([x0, pad + 30 * S, x0 + sum(cols), y], outline="#D0D0D6", width=S)
y += 16 * S; d.text((pad, y), total, font=reg, fill="#1A1A1A")
y += 36 * S
for cl in clines:
    d.text((pad, y), cl, font=reg, fill="#1A1A1A"); y += 24 * S
im.save(out); print(out, im.size)
