"""Создаёт английский README и GiDo/<LANG>/ (README и анимированную графику) из docs_text.py."""
import os
import sys
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from docs_text import LANGUAGES  # noqa: E402

REPO = "https://github.com/Arkomiko/Fruity-Organizer-DataBase"
SITE = "https://arkomiko.github.io/Fruity-Organizer-DataBase/"
LIT, DIM, BACK, PANEL, TEXT = "#FFB23E", "#3C454B", "#262B2F", "#4D565C", "#BDC6CB"
FONT = "Segoe UI, Noto Sans, Helvetica, Arial, sans-serif"
LETTERS = {
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
}


def write(path, text):
    """Записывает текстовый файл."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def banner_svg(lang):
    """Логотип из ячеек: бегунок проходит по столбцам и зажигает их, а под ним сменяются лозунги."""
    pad, gap, letter_gap = 13, 3, 11
    letter_w = 5 * pad + 4 * gap
    grid_h = 7 * pad + 6 * gap
    grid_w = 4 * letter_w + 3 * letter_gap
    width, height = 860, 214
    ox0, oy = (width - grid_w) / 2, 24
    rects, cycle = [], 3.2
    for index, letter in enumerate("FODB"):
        ox = ox0 + index * (letter_w + letter_gap)
        for row, pattern in enumerate(LETTERS[letter]):
            for col, value in enumerate(pattern):
                x = ox + col * (pad + gap)
                y = oy + row * (pad + gap)
                delay = (x - ox0) / grid_w * cycle * 0.72
                if value == "#":
                    rects.append(f'<rect class="on" x="{x:g}" y="{y:g}" width="{pad}" height="{pad}" rx="2.5" style="animation-delay:{delay:.2f}s"/>')
                else:
                    rects.append(f'<rect class="off" x="{x:g}" y="{y:g}" width="{pad}" height="{pad}" rx="2.5" style="animation-delay:{delay:.2f}s"/>')
    direction = ' direction="rtl"' if lang.get("rtl") else ""
    # Лозунги показываются по очереди: у каждого своя задержка в общем цикле.
    slogan_seconds = 4
    slogan_cycle = slogan_seconds * len(lang["taglines"])
    slogans = "\n".join(
        f'<text class="tag{" first" if i == 0 else ""}" x="{width / 2}" y="{oy + grid_h + 54}" text-anchor="middle"{direction} '
        f'style="animation-delay:{i * slogan_seconds}s">{escape(slogan)}</text>'
        for i, slogan in enumerate(lang["taglines"]))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="FODB">
<style>
.on{{fill:{LIT};animation:hit {cycle}s ease-out infinite}}
.off{{fill:{DIM};animation:tick {cycle}s ease-out infinite}}
.title{{font:600 13px {FONT};letter-spacing:6px;fill:#8B959B}}
.tag{{font:15px {FONT};fill:{TEXT};opacity:0;animation:slogan {slogan_cycle}s ease-in-out infinite both}}
@keyframes hit{{0%,100%{{fill:{LIT};opacity:.86}}4%{{fill:#FFE3AE;opacity:1}}20%{{fill:{LIT};opacity:.86}}}}
@keyframes tick{{0%,100%{{fill:{DIM}}}4%{{fill:#6A747A}}18%{{fill:{DIM}}}}}
@keyframes slogan{{0%{{opacity:0;transform:translateY(8px)}}3%,30%{{opacity:1;transform:none}}33%,100%{{opacity:0;transform:translateY(-6px)}}}}
@media (prefers-reduced-motion:reduce){{.on,.off,.tag{{animation:none}}.first{{opacity:1}}}}
</style>
<rect width="{width}" height="{height}" rx="12" fill="{BACK}"/>
{''.join(rects)}
<text class="title" x="{width / 2}" y="{oy + grid_h + 28}" text-anchor="middle">FRUITY ORGANIZER DATABASE</text>
{slogans}
</svg>
'''


def workflow_svg(lang):
    """Плагины летят из списка Installed в дерево папок, а оно меняет раскладки."""
    width, height = 860, 300
    vendor, purpose = lang["vendor"], lang["purpose"]
    reverb, delay, synth = lang["reverb"], lang["delay"], lang["synth"]
    names = ["Peel Compressor", "Basalt Reverb", "Halo Shimmer", "Comet Doubler", "Tangelo Synth", "Ripple Echo"]
    targets = [62, 104, 104, 188, 230, 146]
    cycle = 12
    tiles, keyframes = [], []
    for i, name in enumerate(names):
        y = 66 + i * 34
        keyframes.append(
            f"@keyframes fly{i}{{0%,{4 + i * 3}%{{transform:none;opacity:1}}"
            f"{16 + i * 3}%,88%{{transform:translate(372px,{targets[i] + 20 - y}px) scale(.92);opacity:.0}}"
            f"96%,100%{{transform:none;opacity:1}}}}")
        tiles.append(f'<g style="animation:fly{i} {cycle}s ease-in-out infinite"><rect x="36" y="{y - 14}" width="176" height="28" rx="4" fill="#313A40" stroke="#273036"/>'
                     f'<circle cx="52" cy="{y}" r="4" fill="{LIT}"/><text x="64" y="{y + 4}" class="t">{name}</text></g>')

    def tree(cls, rows):
        """Анимированное дерево одной раскладки."""
        out = [f'<g class="{cls}">']
        for depth, label, y, is_title in rows:
            x = 470 + depth * 22
            out.append(f'<path d="M{x} {y - 8}h6l3 3h11v12h-20z" fill="none" stroke="{LIT if depth == 0 else "#8B959B"}" stroke-width="1.3"/>')
            out.append(f'<text x="{x + 28}" y="{y + 4}" class="{"h" if is_title else "t"}">{escape(label)}</text>')
        return "".join(out) + "</g>"

    trees = [
        tree("l1", [(0, "Citrus Audio", 70, True), (1, reverb, 98, False), (1, delay, 126, False), (0, "Granite DSP", 164, True), (1, reverb, 192, False), (1, synth, 220, False)]),
        tree("l2", [(0, reverb, 70, True), (1, "Citrus Audio", 98, False), (1, "Granite DSP", 126, False), (0, delay, 164, True), (1, "Citrus Audio", 192, False), (0, synth, 228, True)]),
        tree("l3", [(0, reverb, 70, True), (0, delay, 110, True), (0, synth, 150, True), (0, "Citrus Audio", 190, True), (0, "Granite DSP", 230, True)]),
    ]
    captions = [f"{vendor} \\ {purpose}", f"{purpose} \\ {vendor}", purpose]
    labels = "".join(f'<text class="cap c{i + 1}" x="640" y="34" text-anchor="middle">{escape(text)}</text>' for i, text in enumerate(captions))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{escape(lang["layouts"])}">
<style>
.t{{font:12.5px {FONT};fill:{TEXT}}}
.h{{font:600 13px {FONT};fill:#E8EDF0}}
.cap{{font:600 13px {FONT};fill:{LIT}}}
.k{{font:600 13px {FONT};fill:#8B959B}}
.l1,.c1{{animation:a {cycle}s infinite}}
.l2,.c2{{animation:b {cycle}s infinite}}
.l3,.c3{{animation:c {cycle}s infinite}}
@keyframes a{{0%,30%{{opacity:1}}34%,96%{{opacity:0}}100%{{opacity:1}}}}
@keyframes b{{0%,30%{{opacity:0}}34%,63%{{opacity:1}}67%,100%{{opacity:0}}}}
@keyframes c{{0%,63%{{opacity:0}}67%,96%{{opacity:1}}100%{{opacity:0}}}}
.arrow{{stroke-dasharray:8 8;animation:flow 1s linear infinite}}
@keyframes flow{{to{{stroke-dashoffset:-16}}}}
{"".join(keyframes)}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}.l2,.l3,.c2,.c3{{opacity:0}}}}
</style>
<rect width="{width}" height="{height}" rx="12" fill="{BACK}"/>
<rect x="24" y="44" width="200" height="232" rx="6" fill="{PANEL}"/>
<rect x="452" y="44" width="384" height="232" rx="6" fill="{PANEL}"/>
<text class="k" x="124" y="34" text-anchor="middle">{escape(lang["installed"])}</text>
{labels}
<path class="arrow" d="M240 160h190" fill="none" stroke="{LIT}" stroke-width="2"/>
<path d="M430 152l12 8-12 8z" fill="{LIT}"/>
{"".join(trees)}
{"".join(tiles)}
</svg>
'''


def themes_svg(lang):
    """Маленькое окно, которое плавно меняет четыре темы."""
    width, height = 860, 250
    palettes = [("#5B6469", "#4D565C", "#313A40", "#FFB23E", "#E85028", "#1565B8"),
                ("#47403B", "#3A332E", "#26211D", "#F67A3C", "#F05C2E", "#A85A2C"),
                ("#2E3C34", "#25322B", "#18221C", "#4AE4A8", "#48D68C", "#2E8A5E"),
                ("#D9D5CF", "#E9E6E1", "#F6F4F1", "#B0522A", "#C8642E", "#E0A070"),
                ("#4F3F58", "#40324A", "#2B2133", "#F08CC8", "#E878B8", "#8E4A86")]
    n = len(palettes)
    frames = []
    for slot, name in enumerate(("title", "panel", "row", "acc", "led", "sel")):
        stops = []
        for i, palette in enumerate(palettes):
            start, end = i * 100 / n, (i + 0.72) * 100 / n
            stops.append(f"{start:.1f}%,{end:.1f}%{{fill:{palette[slot]}}}")
        stops.append(f"100%{{fill:{palettes[0][slot]}}}")
        frames.append(f"@keyframes {name}{{{''.join(stops)}}}.{name}{{animation:{name} 15s ease-in-out infinite}}")
    rows = []
    for r in range(7):
        y = 66 + r * 22
        cls = "sel" if r == 2 else "row"
        rows.append(f'<rect class="{cls}" x="260" y="{y}" width="540" height="21"/>')
        width_a = 90 + (r * 37) % 70
        rows.append(f'<rect x="276" y="{y + 8}" width="{width_a}" height="5" rx="2" fill="#AEB7BC" opacity=".75"/>')
        rows.append(f'<rect x="480" y="{y + 8}" width="56" height="5" rx="2" fill="#AEB7BC" opacity=".45"/>')
        rows.append(f'<rect x="600" y="{y + 8}" width="{70 + (r * 23) % 60}" height="5" rx="2" fill="#AEB7BC" opacity=".45"/>')
        rows.append(f'<circle class="acc" cx="{262 + 4}" cy="{y + 10}" r="0"/>')
    leds = "".join(f'<circle class="{"led" if i % 3 != 2 else "row"}" cx="88" cy="{112 + i * 24}" r="6.5"/><rect x="104" y="{109 + i * 24}" width="{96 - (i * 13) % 40}" height="6" rx="2" fill="#AEB7BC" opacity=".6"/>' for i in range(5))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="{escape(lang["themes"])}">
<style>
{"".join(frames)}
.c{{font:13px {FONT};fill:{TEXT}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<rect width="{width}" height="{height}" rx="12" fill="{BACK}"/>
<rect class="title" x="60" y="20" width="740" height="26" rx="4"/>
<rect class="panel" x="60" y="46" width="740" height="168"/>
<rect class="row" x="72" y="54" width="170" height="24" rx="3"/>
<rect class="acc" x="110" y="63" width="92" height="6" rx="2"/>
<rect class="row" x="72" y="90" width="170" height="118" rx="3"/>
{leds}
{"".join(rows)}
<text class="c" x="430" y="236" text-anchor="middle">{escape(lang["caption_themes"])}</text>
</svg>
'''


def pill_svg(lang, active):
    """Кнопка языка в виде SVG."""
    width = max(70, 26 + len(lang["name"]) * (13 if not lang["name"].isascii() else 7.4))
    fill, ink = (LIT, "#1A1D20") if active else (DIM, TEXT)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="26" viewBox="0 0 {width:.0f} 26" role="img" aria-label="{escape(lang["name"])}">'
            f'<rect width="{width:.0f}" height="26" rx="5" fill="{fill}"/>'
            f'<text x="{width / 2:.1f}" y="17.5" text-anchor="middle" font-family="{FONT}" font-size="12.5" font-weight="600" fill="{ink}">{escape(lang["name"])}</text></svg>\n')


def switcher(current, to_root):
    """Строка переключения языков."""
    links = []
    for code, lang in LANGUAGES.items():
        suffix = "on" if code == current else "off"
        target = f"{to_root}README.md" if code == "EN-en" else f"{to_root}GiDo/{code}/README.md"
        links.append(f'<a href="{target}"><img src="{to_root}docs/lang/{code}-{suffix}.svg" height="26" alt="{escape(lang["name"])}"></a>')
    return "\n".join(links)


QUERY = '''purpose:reverb,delay                 reverb OR delay
vendor:"plugin alliance" -format:vst  one vendor, without VST2
organized:no kind:synth               synths not organized yet
age:30d bits:64                       64-bit, dated in the last 30 days'''
RULES = '''"purpose_rules": [
  { "purpose": "drums", "name": "kick|808" },
  { "purpose": "vocal", "vendor": "antares" }
]'''
TOKENS = "{vendor}  {purpose}  {format}  {bits}  {letter}  {kind}"
EXAMPLE = "{vendor}\\{purpose}\n{purpose}\\{vendor}\nUSER\\{format}\\{vendor}"


def readme(code, lang, to_root, art):
    """Текст README на одном языке."""
    demo = "demo-ru.gif" if code in ("RU-ru", "UK-ua") else "demo-en.gif"
    body = f'''<p align="center"><img src="{art}banner.svg" alt="FODB" width="100%"></p>

<p align="center">
{switcher(code, to_root)}
</p>

<p align="center"><a href="{REPO}/releases/latest"><b>⬇ {escape(lang["download"])}</b></a> &nbsp;|&nbsp; <a href="{SITE}{code}/wiki/index.html"><b>{escape(lang["wiki"])}</b></a></p>

{lang["intro"]}

<p align="center"><img src="{to_root}docs/{demo}" alt="FODB" width="100%"></p>

## {lang["features"]}

- {lang["f1"]}
- {lang["f2"]}
- {lang["f3"]}
- {lang["f4"]}
- {lang["f5"]}
- {lang["f6"]}
- {lang["f7"]}

## {lang["quick"]}

1. {lang["q1"]}
2. {lang["q2"]}
3. {lang["q3"]}

## {lang["layouts"]}

<p align="center"><img src="{art}workflow.svg" alt="{escape(lang["layouts"])}" width="100%"></p>

{lang["layouts_t"]}

```text
{TOKENS}

{EXAMPLE}
```

## {lang["filters"]}

{lang["filters_t"]}

```text
{QUERY}
```

## {lang["themes"]}

<p align="center"><img src="{art}themes.svg" alt="{escape(lang["themes"])}" width="100%"></p>

{lang["themes_t"]}

## {lang["safety"]}

- {lang["s1"]}
- {lang["s2"]}
- {lang["s3"]}

## {lang["advanced"]}

{lang["advanced_t"]}

```json
{RULES}
```

## {lang["build"]}

{lang["build_t"]}

```powershell
./build.ps1
```

## {lang["credits"]}

{lang["credits_t"]}

{lang["disclaimer"]}
'''
    if lang.get("rtl"):
        body = f'<div dir="rtl">\n\n{body}\n</div>\n'
    return body


def main():
    """Создаёт все файлы документации."""
    required = set(LANGUAGES["EN-en"]) - {"rtl"}
    for code, lang in LANGUAGES.items():
        missing = required - set(lang)
        if missing:
            raise SystemExit(f"{code}: missing {sorted(missing)}")
    if len(LANGUAGES) != 26:
        raise SystemExit("expected 26 languages")
    for code, lang in LANGUAGES.items():
        folder = os.path.join(ROOT, "GiDo", code)
        write(os.path.join(folder, "banner.svg"), banner_svg(lang))
        write(os.path.join(folder, "workflow.svg"), workflow_svg(lang))
        write(os.path.join(folder, "themes.svg"), themes_svg(lang))
        write(os.path.join(folder, "README.md"), readme(code, lang, "../../", ""))
        for suffix, active in (("on", True), ("off", False)):
            write(os.path.join(ROOT, "docs", "lang", f"{code}-{suffix}.svg"), pill_svg(lang, active))
    write(os.path.join(ROOT, "README.md"), readme("EN-en", LANGUAGES["EN-en"], "", "GiDo/EN-en/"))
    print("languages:", len(LANGUAGES))


if __name__ == "__main__":
    main()
