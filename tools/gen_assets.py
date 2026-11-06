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


# Лисичка Arkomiko: контур и глаза в координатах исходного рисунка.
FOX_LINE = [(600, 460), (820, 700), (1110, 700), (1330, 460), (1476, 872), (968, 1478), (456, 872)]
FOX_EYES = ([(637, 936), (782, 954), (880, 1062), (746, 1043)], [(1294, 936), (1149, 954), (1051, 1062), (1185, 1043)])
FOX_SIZE = 40


def _fox_point(x, y):
    """Переводит точку рисунка в координаты значка."""
    scale = (FOX_SIZE - 2) / 1053
    return ((x - 442) * scale + (FOX_SIZE - 1048 * scale) / 2) * SS, ((y - 440) * scale + 1) * SS


def fox_line():
    """Контур лисички."""
    img = canvas(FOX_SIZE)
    points = [_fox_point(x, y) for x, y in FOX_LINE]
    ImageDraw.Draw(img).line(points + points[:2], fill=(255, 255, 255, 255), width=SS, joint="curve")
    return img


def fox_eyes(openness):
    """Глаза лисички. openness: 1 открыты, 0 закрыты (остаётся тонкая линия)."""
    img = canvas(FOX_SIZE)
    d = ImageDraw.Draw(img)
    for eye in FOX_EYES:
        middle = sum(y for _x, y in eye) / len(eye)
        d.polygon([_fox_point(x, middle + (y - middle) * max(openness, 0.08)) for x, y in eye], fill=(255, 255, 255, 255))
    return img


def icon_play():
    """Значок «играть»."""
    img = canvas(16)
    ImageDraw.Draw(img).polygon([(4.5 * SS, 2.5 * SS), (13 * SS, 8 * SS), (4.5 * SS, 13.5 * SS)], fill=(255, 255, 255, 255))
    return img


def icon_stop():
    """Значок «стоп»."""
    img = canvas(16)
    ImageDraw.Draw(img).rectangle((3.5 * SS, 3.5 * SS, 12.5 * SS - 1, 12.5 * SS - 1), fill=(255, 255, 255, 255))
    return img


def icon_arrow(forward):
    """Стрелка вперёд или назад."""
    img = canvas(16)
    d = ImageDraw.Draw(img)
    c = (255, 255, 255, 255)
    points = ((2.5, 8), (13, 8)), ((8.5, 3.5), (13, 8), (8.5, 12.5))
    for line in points:
        d.line([((x if forward else 16 - x) * SS, y * SS) for x, y in line], fill=c, width=int(1.7 * SS), joint="curve")
    return img


def _icon_line(points, width=1.5):
    """Значок из одной линии. Точки заданы в клетках значка 16 на 16."""
    img = canvas(16)
    ImageDraw.Draw(img).line([(x * SS, y * SS) for x, y in points], fill=(255, 255, 255, 255), width=int(width * SS), joint="curve")
    return img


def icon_play_big():
    """Большой значок «играть»."""
    img = canvas(22)
    ImageDraw.Draw(img).polygon([(6 * SS, 3.5 * SS), (18 * SS, 11 * SS), (6 * SS, 18.5 * SS)], fill=(255, 255, 255, 255))
    return img


def icon_stop_big():
    """Большой значок «стоп»."""
    img = canvas(22)
    ImageDraw.Draw(img).rectangle((5 * SS, 5 * SS, 17 * SS - 1, 17 * SS - 1), fill=(255, 255, 255, 255))
    return img


def icon_sine():
    """Синусоида."""
    return _icon_line([(1 + x / 2, 8 - 4.5 * math.sin(math.pi * x / 14)) for x in range(29)])


def icon_triangle():
    """Треугольная волна: значок-треугольник."""
    return _icon_line([(8, 2.5), (14, 13), (2, 13), (8, 2.5), (14, 13)])


def icon_square():
    """Квадратная волна: значок-квадрат."""
    return _icon_line([(3, 3), (13, 3), (13, 13), (3, 13), (3, 3), (13, 3)])


def icon_bell():
    """Колокол: значок-крестик."""
    img = _icon_line([(3, 3), (13, 13)], 1.7)
    ImageDraw.Draw(img).line([(13 * SS, 3 * SS), (3 * SS, 13 * SS)], fill=(255, 255, 255, 255), width=int(1.7 * SS))
    return img


def icon_scale():
    """Лад: ступени."""
    return _icon_line([(1.5, 14), (5, 14), (5, 10), (8.8, 10), (8.8, 6), (12.5, 6), (12.5, 2), (15, 2)])


def icon_help():
    """Знак вопроса."""
    img = canvas(16)
    d = ImageDraw.Draw(img)
    c = (255, 255, 255, 255)
    width = int(1.8 * SS)
    d.arc((4.2 * SS, 1.6 * SS, 11.8 * SS, 9.2 * SS), 180, 50, fill=c, width=width)
    d.line([(10.2 * SS, 8.2 * SS), (8 * SS, 9.8 * SS), (8 * SS, 11 * SS)], fill=c, width=width, joint="curve")
    d.ellipse((6.9 * SS, 12.4 * SS, 9.1 * SS, 14.6 * SS), fill=c)
    return img


def icon_web():
    """Планета: круг, меридиан и параллели."""
    img = canvas(16)
    d = ImageDraw.Draw(img)
    c = (255, 255, 255, 255)
    width = int(1.15 * SS)
    d.ellipse((1.2 * SS, 1.2 * SS, 14.8 * SS, 14.8 * SS), outline=c, width=width)
    d.ellipse((4.9 * SS, 1.2 * SS, 11.1 * SS, 14.8 * SS), outline=c, width=width)
    for y in (5.2, 10.8):
        d.line([(2.2 * SS, y * SS), (13.8 * SS, y * SS)], fill=c, width=width)
    return img


def icon_done():
    """Галочка «готово»."""
    img = canvas(16)
    points = ((2.5, 8.5), (6.5, 12.5), (13.5, 4))
    ImageDraw.Draw(img).line([(x * SS, y * SS) for x, y in points], fill=(255, 255, 255, 255), width=int(1.9 * SS), joint="curve")
    return img


def icon_sound(muted):
    """Значок звука: динамик с волнами или с крестиком."""
    img = canvas(16)
    d = ImageDraw.Draw(img)
    c = (255, 255, 255, 255)
    d.polygon([(x * SS, y * SS) for x, y in ((1.5, 6), (4, 6), (8, 2.5), (8, 13.5), (4, 10), (1.5, 10))], fill=c)
    if muted:
        d.line([(10.5 * SS, 5.5 * SS), (15 * SS, 10.5 * SS)], fill=c, width=int(1.3 * SS))
        d.line([(15 * SS, 5.5 * SS), (10.5 * SS, 10.5 * SS)], fill=c, width=int(1.3 * SS))
    else:
        d.arc((6.5 * SS, 4.5 * SS, 12 * SS, 11.5 * SS), -55, 55, fill=c, width=int(1.1 * SS))
        d.arc((6.5 * SS, 2 * SS, 15 * SS, 14 * SS), -55, 55, fill=c, width=int(1.1 * SS))
    return img


def _export_tray(d):
    """Лоток внизу значка: общий знак экспорта."""
    c = (255, 255, 255, 255)
    d.rectangle((1.5 * SS, 13.5 * SS, 14.5 * SS - 1, 15 * SS - 1), fill=c)


def icon_wav():
    """Значок экспорта WAV: волна над лотком."""
    img = canvas(16)
    d = ImageDraw.Draw(img)
    _export_tray(d)
    for x, half in ((2.5, 1.5), (5, 3.5), (7.5, 5), (10, 3), (12.5, 1.5)):
        d.rectangle(((x - 0.6) * SS, (6.5 - half) * SS, (x + 0.6) * SS, (6.5 + half) * SS), fill=(255, 255, 255, 255))
    return img


def icon_midi():
    """Значок экспорта MIDI: клавиши над лотком."""
    img = canvas(16)
    d = ImageDraw.Draw(img)
    _export_tray(d)
    c = (255, 255, 255, 255)
    d.rectangle((2 * SS, 1.5 * SS, 14 * SS - 1, 11.5 * SS - 1), fill=c)
    for x in (5.5, 9.5):  # щели между белыми клавишами
        d.rectangle((x * SS, 7 * SS, (x + 1) * SS - 1, 11.5 * SS), fill=(0, 0, 0, 0))
    for x in (4.5, 8.5, 12.0):  # чёрные клавиши вырезаны из заливки
        d.rectangle(((x - 0.9) * SS, 1.5 * SS, (x + 0.9) * SS, 7 * SS), fill=(0, 0, 0, 0))
    return img


GLYPHS = {
    "filter": funnel,
    # Значки с приставками fx_ и ic_ окрашиваются по запросу, только когда нужны.
    "fx_line": fox_line, "fx_eye0": lambda: fox_eyes(1.0), "fx_eye1": lambda: fox_eyes(0.45), "fx_eye2": lambda: fox_eyes(0.0),
    "ic_play": icon_play, "ic_stop": icon_stop, "ic_sound": lambda: icon_sound(False), "ic_mute": lambda: icon_sound(True),
    "ic_wav": icon_wav, "ic_midi": icon_midi,
    "ic_prev": lambda: icon_arrow(False), "ic_next": lambda: icon_arrow(True), "ic_done": icon_done,
    "ic_help": icon_help, "ic_web": icon_web,
    "ic_sine": icon_sine, "ic_triangle": icon_triangle, "ic_square": icon_square, "ic_bell": icon_bell, "ic_scale": icon_scale,
    "ic_play_big": icon_play_big, "ic_stop_big": icon_stop_big,
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
    "F": ("####", "#...", "#...", "###.", "#...", "#...", "#..."),
    "O": (".##.", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."),
    "D": ("###.", "#..#", "#..#", "#..#", "#..#", "#..#", "###."),
    "B": ("###.", "#..#", "#..#", "###.", "#..#", "#..#", "###."),
}
LIT = "#FFB23E"
DIM = "#3C454B"
BACK = "#262B2F"


def logo_svg(text_line=True):
    """Логотип FODB в SVG."""
    pad, gap, letter_gap, margin = 16, 3, 13, 22
    letter_w = 4 * pad + 3 * gap
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
    """Значок программы: F и B такими же буквами в 4 столбца, как в логотипе."""
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, size - 8, size - 8), 72, fill=BACK)
    pad, gap, letter_gap = 50, 6, 20
    block_w = 4 * pad + 3 * gap
    block_h = 7 * pad + 6 * gap
    # Две строки букв не читались бы, поэтому на значке F и B, первая и последняя буквы.
    total = 2 * block_w + letter_gap
    x0, y0 = (size - total) // 2, (size - block_h) // 2
    for index, letter in enumerate("FB"):
        ox = x0 + index * (block_w + letter_gap)
        for row, pattern in enumerate(LETTERS[letter]):
            for col, value in enumerate(pattern):
                x = ox + col * (pad + gap)
                y = y0 + row * (pad + gap)
                d.rounded_rectangle((x, y, x + pad, y + pad), 8, fill=LIT if value == "#" else DIM)
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
