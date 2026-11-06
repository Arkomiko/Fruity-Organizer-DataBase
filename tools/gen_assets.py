"""Рисует значки интерфейса (только при сборке, нужен Pillow) и пишет src/assets_data.py и assets/app.ico."""
import base64
import math
import os
import zlib

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCALES = (1.0, 1.25, 1.5, 2.0)
SS = 8  # во сколько раз рисуем крупнее для сглаживания


def canvas(size):
    """Пустое изображение с запасом для сглаживания."""
    return Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))


def star_points(size, inner=0.40):
    """Вершины звезды."""
    c = size / 2
    r = size * 0.47
    points = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        radius = r if i % 2 == 0 else r * inner
        points.append((c + radius * math.cos(a), c * 1.06 + radius * math.sin(a)))
    return points


def star(on):
    """Значок звезды."""
    img = canvas(14)
    d = ImageDraw.Draw(img)
    pts = star_points(14 * SS)
    if on:
        d.polygon(pts, fill=(255, 176, 58, 255))
    else:
        d.line(pts + pts[:2], fill=(92, 103, 110, 255), width=int(0.9 * SS), joint="curve")
    return img


def check():
    """Значок галочки."""
    img = canvas(14)
    ImageDraw.Draw(img).line([(2.5 * SS, 7.5 * SS), (5.5 * SS, 11 * SS), (11.5 * SS, 3 * SS)],
                             fill=(186, 196, 202, 255), width=int(1.3 * SS), joint="curve")
    return img


def folder_shape(d, x0=1.5, y0=2.5, x1=14.5, y1=12.5, w=1.0):
    """Контур папки. Центры линий на полупикселях: штрих 1px остаётся чётким при 100 %."""
    points = [(x0, y1), (x0, y0), (x0 + 4.5, y0), (x0 + 6.5, y0 + 2), (x1, y0 + 2), (x1, y1), (x0, y1)]
    d.line([(px * SS, py * SS) for px, py in points], fill=(255, 255, 255, 255), width=int(w * SS), joint="curve")


def folder():
    """Значок папки."""
    img = canvas(16)
    folder_shape(ImageDraw.Draw(img))
    return img


def folder_badge(kind):
    """Папка с плюсом или крестиком."""
    img = canvas(18)
    d = ImageDraw.Draw(img)
    folder_shape(d, 1.5, 2.5, 12.5, 11.5)
    d.rectangle((9.5 * SS, 9 * SS, 18 * SS, 18 * SS), fill=(0, 0, 0, 0))
    c = (255, 255, 255, 255)
    if kind == "plus":
        d.rectangle((13 * SS, 10 * SS, 14 * SS, 16 * SS), fill=c)
        d.rectangle((11 * SS, 12.5 * SS, 16 * SS, 13.5 * SS), fill=c)
    else:
        d.line([(11 * SS, 10.5 * SS), (15.5 * SS, 15 * SS)], fill=c, width=SS)
        d.line([(15.5 * SS, 10.5 * SS), (11 * SS, 15 * SS)], fill=c, width=SS)
    return img


def win_glyph(kind):
    """Кнопки окна."""
    img = canvas(16)
    d = ImageDraw.Draw(img)
    c = (255, 255, 255, 255)
    if kind == "min":
        d.rectangle((4 * SS, 11 * SS, 11 * SS - 1, 13 * SS - 1), fill=c)
    elif kind == "max":
        d.rectangle((3 * SS, 4 * SS, 12 * SS - 1, 12 * SS - 1), fill=c)
        d.rectangle((4 * SS, 6 * SS, 11 * SS - 1, 11 * SS - 1), fill=(0, 0, 0, 0))
    elif kind == "close":
        w = int(1.5 * SS)
        d.line([(4 * SS, 4 * SS), (12 * SS, 12 * SS)], fill=c, width=w)
        d.line([(12 * SS, 4 * SS), (4 * SS, 12 * SS)], fill=c, width=w)
        d.rectangle((7 * SS, 7 * SS, 9 * SS - 1, 9 * SS - 1), fill=c)
    return img


def chevron(up, color=(128, 138, 145, 255)):
    """Стрелка вверх или вниз."""
    img = canvas(10)
    pts = [(1.5, 6.5), (5, 3.5), (8.5, 6.5)] if up else [(1.5, 3.5), (5, 6.5), (8.5, 3.5)]
    ImageDraw.Draw(img).line([(x * SS, y * SS) for x, y in pts], fill=color, width=int(1.1 * SS), joint="curve")
    return img


def funnel():
    """Значок фильтра."""
    img = canvas(16)
    d = ImageDraw.Draw(img)
    points = [(2, 3), (14, 3), (9.5, 8.5), (9.5, 13), (6.5, 11.5), (6.5, 8.5)]
    d.polygon([(x * SS, y * SS) for x, y in points], fill=(255, 255, 255, 255))
    return img


GLYPHS = {
    "filter": funnel,
    "star_on": lambda: star(True), "star_off": lambda: star(False),
    "check": check, "folder": folder,
    "folder_plus": lambda: folder_badge("plus"), "folder_x": lambda: folder_badge("x"),
    "win_min": lambda: win_glyph("min"), "win_max": lambda: win_glyph("max"), "win_close": lambda: win_glyph("close"),
    "up": lambda: chevron(True), "down": lambda: chevron(False),
}


def packed_mask(img, scale):
    """Хранит только прозрачность: цвет задаётся темой при запуске."""
    side = max(1, round(img.width // SS * scale))
    mask = img.getchannel("A").resize((side, side), Image.BOX)
    return side, base64.b64encode(zlib.compress(mask.tobytes(), 9)).decode("ascii")


# Логотип FODB: каждая буква это рисунок на сетке ячеек секвенсора.
LETTERS = {
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
}
MINI = {
    "F": ("###", "#..", "##.", "#..", "#.."),
    "O": ("###", "#.#", "#.#", "#.#", "###"),
    "D": ("##.", "#.#", "#.#", "#.#", "##."),
    "B": ("##.", "#.#", "##.", "#.#", "##."),
}
LIT = "#FFB23E"
DIM = "#3C454B"
BACK = "#262B2F"


def logo_svg(text_line=True):
    """Логотип FODB в SVG."""
    pad, gap, letter_gap, margin = 16, 3, 13, 22
    letter_w = 5 * pad + 4 * gap
    grid_h = 7 * pad + 6 * gap
    width = margin * 2 + 4 * letter_w + 3 * letter_gap
    height = margin * 2 + grid_h + (34 if text_line else 0)
    rects = []
    for index, letter in enumerate("FODB"):
        ox = margin + index * (letter_w + letter_gap)
        for row, pattern in enumerate(LETTERS[letter]):
            for col, value in enumerate(pattern):
                fill = LIT if value == "#" else DIM
                rects.append(f'<rect x="{ox + col * (pad + gap)}" y="{margin + row * (pad + gap)}" '
                             f'width="{pad}" height="{pad}" rx="3" fill="{fill}"/>')
    caption = ""
    if text_line:
        caption = (f'<text x="{width / 2}" y="{height - 21}" text-anchor="middle" fill="#BDC6CB" '
                   'font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="17" letter-spacing="5">'
                   'FRUITY ORGANIZER DATABASE</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'role="img" aria-label="FODB"><rect width="{width}" height="{height}" rx="14" fill="{BACK}"/>'
            + "".join(rects) + caption + "</svg>\n")


def app_icon():
    """Значок программы: F и B горящими ячейками, достаточно крупными для малых размеров."""
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, size - 8, size - 8), 72, fill=BACK)
    pad, gap, letter_gap = 56, 10, 40
    block_w = 3 * pad + 2 * gap
    block_h = 5 * pad + 4 * gap
    # Две строки букв не читались бы, поэтому на значке F и B, первая и последняя буквы.
    total = 2 * block_w + letter_gap
    x0, y0 = (size - total) // 2, (size - block_h) // 2
    for index, letter in enumerate("FB"):
        ox = x0 + index * (block_w + letter_gap)
        for row, pattern in enumerate(MINI[letter]):
            for col, value in enumerate(pattern):
                x = ox + col * (pad + gap)
                y = y0 + row * (pad + gap)
                d.rounded_rectangle((x, y, x + pad, y + pad), 9, fill=LIT if value == "#" else DIM)
    return img


def main():
    """Создаёт все файлы."""
    data = {}
    for scale in SCALES:
        data[scale] = {name: packed_mask(make(), scale) for name, make in GLYPHS.items()}
    target = os.path.join(ROOT, "src", "assets_data.py")
    with open(target, "w", encoding="ascii", newline="\n") as f:
        f.write('"""Generated by tools/gen_assets.py: icon alpha masks as (side, base64 zlib bytes) per scale."""\nDATA = {\n')
        for scale, items in data.items():
            f.write(f"    {scale}: {{\n")
            for name, value in items.items():
                f.write(f'        "{name}": ({value[0]}, "{value[1]}"),\n')
            f.write("    },\n")
        f.write("}\n")
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    icon = app_icon()
    icon.save(os.path.join(ROOT, "assets", "app.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    os.makedirs(os.path.join(ROOT, "GiDo"), exist_ok=True)
    for name, with_text in (("logo.svg", True), ("logo-mark.svg", False)):
        with open(os.path.join(ROOT, "GiDo", name), "w", encoding="ascii", newline="\n") as f:
            f.write(logo_svg(with_text))
    print("assets written:", os.path.getsize(target), "bytes")


if __name__ == "__main__":
    main()
