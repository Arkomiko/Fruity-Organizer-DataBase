"""Записывает демо для документации из настоящей программы на выдуманной базе плагинов.

Запуск: make_demo.py <en|ru> (нужен Pillow; пишет docs/demo-<язык>.gif и docs/screenshot-*-<язык>.png)
"""
import ctypes
import os
import shutil
import sys
import tempfile
import time
from ctypes import wintypes

from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import i18n  # noqa: E402

LANG = sys.argv[1] if len(sys.argv) > 1 else "en"
i18n.set_language(LANG)
import core  # noqa: E402
import rules  # noqa: E402
import ui  # noqa: E402

CATALOG = {
    "Citrus Audio": ["Peel Compressor", "Zest EQ", "Pulp Saturator", "Rind Limiter", "Juice Chorus", "Seed Delay"],
    "Granite DSP": ["Basalt Reverb", "Quartz Clipper", "Slate Gate", "Marble Plate", "Flint Transient", "Shale Filter"],
    "Lumen Sound": ["Halo Shimmer", "Prism Stereo", "Beam Exciter", "Glow Tape", "Aurora Phaser", "Spark De-Esser"],
    "Nova Labs": ["Orbit Flanger", "Comet Doubler", "Nebula Convolver", "Quasar Bus", "Photon Meter"],
    "Pulsewave": ["Tremor", "Sidechain Pro", "Drift Vibrato", "Ripple Echo", "Surge Maximizer", "Static Crusher"],
    "Tideline": ["Undertow Bass EQ", "Riptide Ducker", "Harbor Room", "Swell Compressor"],
    "Verdant Instruments": ["Fern Pad Filter", "Moss Reverb", "Canopy Widener", "Bloom Glue"],
}
SYNTHS = {
    "Citrus Audio": ["Tangelo Synth", "Kumquat Keys"], "Lumen Sound": ["Lantern Pads"],
    "Nova Labs": ["Pulsar Lead", "Zenith Poly"], "Verdant Instruments": ["Willow Strings"],
}
THEMES = {  # выдуманные темы для записи: ручки и цвета в формате FL Studio
    "ember": {"Hue": "0", "Saturation": "-140", "Lightness": "-120", "Contrast": "0", "Highlight": str(0x3C7AF6),
              "Option": str(0x2E5CF0), "Selected": str(0x2A63D8), "TextColor": str(0xD5DCE6)},
    "mint": {"Hue": "-41", "Saturation": "60", "Lightness": "-150", "Contrast": "-6", "Highlight": str(0xA8E44A),
             "Option": str(0x8CD648), "Selected": str(0x7DB23C), "TextColor": str(0xDCEADC)},
    "paper": {"Hue": "0", "Saturation": "-240", "Lightness": "150", "Contrast": "64", "Highlight": str(0xB0522A),
              "Option": str(0xC8642E), "Selected": str(0xE0A070), "TextColor": str(0x4C3F38)},
    "violet": {"Hue": "85", "Saturation": "90", "Lightness": "-110", "Contrast": "10", "Highlight": str(0xF08CC8),
               "Option": str(0xE878B8), "Selected": str(0xA858A0), "TextColor": str(0xF4E8F0)},
}


def make_database(root: str) -> str:
    """Создаёт базу из выдуманных плагинов."""
    db = os.path.join(root, "FL Studio", "Presets", "Plugin database")
    installed = os.path.join(db, "Installed")
    index = []

    def add(kind_dir, plug_type, vendor, name, fmt):
        """Добавляет один плагин."""
        key = f"{kind_dir}\\{fmt}\\{name}"
        folder = os.path.join(installed, kind_dir, fmt)
        os.makedirs(folder, exist_ok=True)
        ext = {"VST3": ".vst3", "CLAP": ".clap", "VST": "_x64.dll"}[fmt]
        base = {"VST3": r"C:\Program Files\Common Files\VST3", "CLAP": r"C:\Program Files\Common Files\CLAP",
                "VST": r"C:\Program Files\VstPlugins"}[fmt]
        body = (f"fileversion=2\r\nps_name={name}\r\nps_files=1\r\nps_file_name_0={name}\r\n"
                f"ps_file_filename_0={base}\\{vendor}\\{name}{ext}\r\nps_file_type_0={plug_type}\r\nps_file_bitsize_0=64\r\n"
                f"ps_file_scanflags_0=1\r\nps_file_vendorname_0={vendor}\r\n")
        with open(os.path.join(folder, name + ".nfo"), "w", encoding="utf-8", newline="") as f:
            f.write(body)
        raw = vendor.encode()
        with open(os.path.join(folder, name + ".fst"), "wb") as f:
            f.write(b"FLhd" + b"\x01" * 60 + b"8\0\0\0" + len(raw).to_bytes(4, "little") + b"\0\0\0\0" + raw)
        index.append(f"[{key}]\r\n{body}\r\n")

    for vendor, names in CATALOG.items():
        for position, name in enumerate(names):
            add("Effects", "1", vendor, name, "VST3")
            if position % 2 == 0:
                add("Effects", "1", vendor, name, "VST")
            if position % 3 == 0:
                add("Effects", "1", vendor, name, "CLAP")
    for vendor, names in SYNTHS.items():
        for name in names:
            add("Generators", "2", vendor, name, "VST3")
    with open(os.path.join(installed, core.INDEX_FILE), "w", encoding="utf-8-sig", newline="") as f:
        f.write("".join(index))
    return db


def main() -> None:
    """Проводит сценарий и снимает кадры."""
    work = tempfile.mkdtemp()
    db = make_database(work)
    themes_dir = os.path.join(work, "themes")
    os.makedirs(themes_dir)
    theme_files = {}
    for name, values in THEMES.items():
        theme_files[name] = os.path.join(themes_dir, name + ".flstheme")
        with open(theme_files[name], "w", encoding="utf-8") as f:
            f.writelines(f"{k}={v}\n" for k, v in values.items())

    settings = core.Settings(os.path.join(work))
    settings["theme_mode"] = "classic"
    settings["geometry"] = "1236x679+200+100"
    settings["auto_backup"] = False
    root, app = ui.create_window(settings, db)

    def settle(ms=350):
        """Даёт окну отрисоваться."""
        end = time.time() + ms / 1000
        while time.time() < end:
            root.update()
            time.sleep(0.01)

    def capture(window):
        """Снимок окна через PrintWindow."""
        settle()
        hwnd = ui.hwnd_of(window)
        rect = wintypes.RECT()
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w, h = rect.right - rect.left, rect.bottom - rect.top
        gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
        gdi32.CreateCompatibleDC.restype = wintypes.HDC
        user32.GetWindowDC.restype = wintypes.HDC
        window_dc = user32.GetWindowDC(wintypes.HWND(hwnd))
        dc = gdi32.CreateCompatibleDC(wintypes.HDC(window_dc))
        bitmap = gdi32.CreateCompatibleBitmap(wintypes.HDC(window_dc), w, h)
        gdi32.SelectObject(wintypes.HDC(dc), wintypes.HBITMAP(bitmap))
        user32.PrintWindow(wintypes.HWND(hwnd), wintypes.HDC(dc), 2)
        buffer = ctypes.create_string_buffer(w * h * 4)
        info = (ctypes.c_uint32 * 10)(40, w, ctypes.c_uint32(-h).value, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
        gdi32.GetDIBits(wintypes.HDC(dc), wintypes.HBITMAP(bitmap), 0, h, buffer, info, 0)
        return Image.frombuffer("RGBA", (w, h), buffer, "raw", "BGRA", 0, 1).convert("RGB")

    frames: list[tuple[Image.Image, int]] = []

    def hold(image, ms):
        """Добавляет кадр."""
        frames.append((image, ms))

    def fade(start, end, steps=5, ms=70):
        """Добавляет плавный переход между кадрами."""
        for i in range(1, steps):
            frames.append((Image.blend(start, end, i / steps), ms))

    settle(500)
    first = capture(root)
    first.save(os.path.join(ROOT, "docs", f"screenshot-options-{LANG}.png"), optimize=True)
    hold(first, 1600)

    # Окно предпросмотра поверх главного, затем отмена.
    captured = {}

    def grab_dialog():
        """Снимает диалог и закрывает его."""
        dialogs = [w for w in root.winfo_children() if isinstance(w, ui.tk.Toplevel)]
        if not dialogs:
            root.after(100, grab_dialog)
            return
        top = dialogs[0]
        captured["image"] = capture(top)
        captured["offset"] = (top.winfo_rootx() - root.winfo_rootx(), top.winfo_rooty() - root.winfo_rooty())
        top.event_generate("<Escape>")

    root.after(250, grab_dialog)
    app.organize_click()
    with_dialog = first.copy()
    dim = Image.new("RGB", first.size, (0, 0, 0))
    with_dialog = Image.blend(with_dialog, dim, 0.35)
    with_dialog.paste(captured["image"], captured["offset"])
    fade(first, with_dialog, 3)
    hold(with_dialog, 2400)
    fade(with_dialog, first, 3)

    # Настоящее копирование по производителям: в списке загораются звёзды.
    app.set_layout(rules.LAYOUTS["vendor_purpose"])
    opts = app._options()
    plan = core.build_plan(app.active_plugins(), db, opts, app.folders)
    groups: dict[str, list] = {}
    for action in plan.actions:
        groups.setdefault(action.dest_dir, []).append(action)
    done, total = 0, len(plan.actions)
    previous = first
    for folder, actions in groups.items():
        core.execute(core.Plan(actions=actions), db, opts)
        done += len(actions)
        app.refresh()
        app.set_hint(i18n.tr("Копирование {done} из {total}: {name}").format(done=done, total=total, name=actions[-1].plugin.name))
        frame = capture(root)
        hold(frame, 260)
        previous = frame
    app.set_hint("")
    organized = capture(root)
    hold(organized, 1500)

    # Меню фильтров: отмечаем значения, и список меняется.
    app.toggle_filters()
    settle(300)
    panel = app.filter_panel
    def with_panel():
        """Снимок окна вместе с меню фильтров."""
        base = capture(root)
        offset = (panel.top.winfo_rootx() - root.winfo_rootx(), panel.top.winfo_rooty() - root.winfo_rooty())
        base.paste(capture(panel.top), offset)
        return base
    menu_frame = with_panel()
    fade(organized, menu_frame, 3)
    hold(menu_frame, 1300)
    panel._toggle("purpose", "reverb")
    hold(with_panel(), 1100)
    panel._toggle("purpose", "dynamics")
    filtered = with_panel()
    hold(filtered, 1300)
    panel._reset()
    panel.close()
    settle(200)
    organized = capture(root)
    fade(filtered, organized, 3)

    # Страница «Плагин».
    grid = app.grid
    y = grid.head_h + grid.row_h * 5
    grid.c.event_generate("<Button-1>", x=200, y=y)
    grid.c.event_generate("<ButtonRelease-1>", x=200, y=y)
    app.show_page("plugin")
    plugin_page = capture(root)
    plugin_page.save(os.path.join(ROOT, "docs", f"screenshot-plugin-{LANG}.png"), optimize=True)
    fade(organized, plugin_page, 3)
    hold(plugin_page, 1800)
    app.show_page("options")

    # Синхронизация тем: окно следует за активной темой.
    previous = capture(root)
    fade(plugin_page, previous, 3)
    for name in ("ember", "mint", "paper", "violet"):
        app.forced_theme = theme_files[name]
        app.apply_theme()
        themed = capture(root)
        if name == "mint":
            themed.save(os.path.join(ROOT, "docs", f"screenshot-theme-{LANG}.png"), optimize=True)
        fade(previous, themed)
        hold(themed, 1300)
        previous = themed
    app.forced_theme = None
    app.apply_theme()
    fade(previous, capture(root))

    app.close()
    write_gif(frames, os.path.join(ROOT, "docs", f"demo-{LANG}.gif"))
    shutil.rmtree(work, ignore_errors=True)


def write_gif(frames, path, width=960) -> None:
    """Собирает кадры в GIF."""
    scaled = [(image.resize((width, round(image.height * width / image.width)), Image.LANCZOS), ms) for image, ms in frames]
    # Своя палитра на кадр делает переходы чище; одинаковые кадры сливаются в один длинный.
    merged: list[list] = []
    for image, ms in scaled:
        if merged and ImageChops.difference(merged[-1][0], image).getbbox() is None:
            merged[-1][1] += ms
        else:
            merged.append([image, ms])
    paletted = [image.quantize(colors=128, method=Image.MEDIANCUT, dither=Image.NONE) for image, _ in merged]
    paletted[0].save(path, save_all=True, append_images=paletted[1:], duration=[ms for _, ms in merged], loop=0,
                     optimize=True, disposal=1)
    print(path, len(merged), "frames", round(os.path.getsize(path) / 1048576, 2), "MB")


if __name__ == "__main__":
    main()
