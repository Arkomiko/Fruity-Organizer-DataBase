"""Вкладка «О программе»: живой логотип FODB и спрятанный за ним мини-секвенсор.

Логотип зациклен и на клики не реагирует. Еле заметная лисичка в правом нижнем углу моргает при
наведении, а клик по ней запускает превращение: обводка рамки, затемнение фона, секвенсор.
Перерисовываются только изменившиеся ячейки, а анимация идёт, только пока вкладка видна.
"""
from __future__ import annotations

import math
import tkinter as tk
import tkinter.filedialog as filedialog

import i18n
import sequencer
from theme import mix

FRAME_MS = 33
PATTERNS = 8
AUTHOR_URL = "https://arkomiko.net"
LETTERS = {
    "F": ("####", "#...", "#...", "###.", "#...", "#...", "#..."),
    "O": (".##.", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."),
    "D": ("###.", "#..#", "#..#", "#..#", "#..#", "#..#", "###."),
    "B": ("###.", "#..#", "#..#", "###.", "#..#", "#..#", "###."),
}
ROWS, LETTER_COLUMNS = sequencer.ROWS, 4
COLUMNS = 4 * LETTER_COLUMNS
INTRO_FRAMES = 34  # логотип загорается и по нему проходит волна
CYCLE_FRAMES = 90  # полный круг анимации логотипа
FADE_FRAMES = 14  # логотип плавно гаснет перед новым кругом
ROW_LABELS = ("K1", "K2", "K3", "K4", "Hh", "Sn", "Ki")
DRUM_TIPS = {sequencer.HAT: "Hi-hat", sequencer.SNARE: "Snare", sequencer.KICK: "Kick"}
WHITE_KEYS = (0, 2, 4, 5, 7, 9, 11)
BLACK_KEYS = {1: 1, 3: 2, 6: 4, 8: 5, 10: 6}  # чёрная клавиша: перед какой белой она стоит
SCALE_LABELS = {"minor_pentatonic": "Min5p", "major_pentatonic": "Maj5p", "natural_minor": "Min", "major": "Maj"}
DARKEST = 0.45  # насколько темнеет фон вокруг секвенсора
TRACE_MS, DARKEN_MS, GLIDE_MS = 520, 320, 420
BLINK_FRAMES = (0, 1, 2, 1, 0, 1, 2, 1, 0)  # открыт, прикрыт, закрыт: два взмаха глазками
POP_SIZES = (0.45, 0.8, 1.1, 1.0)  # новая ячейка быстро вырастает и чуть пружинит
DISSOLVE_STEPS = ("gray75", "gray50", "gray25", "gray12")  # стёртая ячейка рассыпается на точки


def logo_pattern() -> set[tuple[int, int]]:
    """Ячейки (столбец, строка), из которых складываются буквы FODB."""
    lit = set()
    for index, letter in enumerate("FODB"):
        for row, pattern in enumerate(LETTERS[letter]):
            lit.update((index * LETTER_COLUMNS + col, row) for col, value in enumerate(pattern) if value == "#")
    return lit


class VerticalSlider:
    """Вертикальный ползунок от 0 внизу до 100 вверху."""

    def __init__(self, canvas, colors: dict, x: int, top: int, bottom: int, value: int, on_change, under: str, p):
        """Рисует ползунок. on_change вызывается при каждом изменении значения."""
        self.c, self.top, self.bottom, self.x, self.value, self.on_change = canvas, top, bottom, x, value, on_change
        self.half_w, self.half_h = p(8), p(4)
        tag = self.tag = f"vslider{id(self)}"
        canvas.create_rectangle(x - p(9), top - p(6), x + p(9), bottom + p(6), fill=under, outline="", tags=tag)
        canvas.create_rectangle(x - p(2), top, x + p(2), bottom, fill=colors["BOX"], outline=colors["BOX_LINE"], tags=tag)
        self.fill = canvas.create_rectangle(x - p(1), bottom, x + p(2), bottom, fill=colors["ORANGE"], outline="", tags=tag)
        self.thumb = canvas.create_rectangle(0, 0, 0, 0, fill=colors["BTN_TOP"], outline=colors["BTN_BORDER"], tags=tag)
        canvas.tag_bind(tag, "<Button-1>", self._drag)
        canvas.tag_bind(tag, "<B1-Motion>", self._drag)
        self._paint()

    def _paint(self) -> None:
        """Ставит заливку и ручку по значению."""
        y = self.bottom - self.value / 100 * (self.bottom - self.top)
        self.c.coords(self.fill, self.x - 1, y, self.x + 2, self.bottom)
        self.c.coords(self.thumb, self.x - self.half_w, y - self.half_h, self.x + self.half_w, y + self.half_h)

    def _drag(self, event) -> None:
        """Переводит положение мыши в значение."""
        value = round(max(0.0, min(1.0, (self.bottom - event.y) / (self.bottom - self.top))) * 100)
        if value != self.value:
            self.value = value
            self._paint()
            self.on_change(value)


class AboutPage:
    """Рисует вкладку и управляет логотипом и секвенсором."""

    def __init__(self, canvas, theme, colors: dict, title: str, version: str, app):
        """Запоминает холст и подключает события мыши."""
        self.c, self.t, self.colors, self.app = canvas, theme, colors, app
        self.title, self.version = title, version
        self.visible = False
        self.running = False
        self.seq_on = False
        self.busy = False  # идёт превращение: клики не принимаются
        self.dark = 0.0
        self.built = False
        self.build_job = None
        self.width = 0
        self.logo = logo_pattern()
        self.patterns = self._load_patterns()  # восемь рисунков, пользователь заполняет их сам
        self.active_pattern = 0
        self.pattern = self.patterns[0]
        self.mixer = sequencer.Mixer(self.pattern)
        self.player: sequencer.Player | None = None
        self.frame = 0
        self.sweeping = True
        self.energy: dict[tuple[int, int], float] = {}
        self.pads: dict[tuple[int, int], int] = {}
        self.painted: dict[int, str] = {}
        self.fading: list[tuple[int, str]] = []
        self.hover = None
        self.stroke = None  # идёт рисование: True ставит ячейки, False стирает
        self.stroke_pad = None
        self.changing: dict[tuple[int, int], list] = {}  # ячейки в анимации: [картинка, кадр, добавлена ли]
        self.fox_hover = False
        self.level = 0.0
        self.tempo_entry = None
        canvas.bind("<Configure>", self._configure)
        canvas.bind("<Button-1>", self._click)
        canvas.bind("<Button-3>", self._erase_press)
        canvas.bind("<B1-Motion>", self._stroke_motion)
        canvas.bind("<B3-Motion>", self._stroke_motion)
        canvas.bind("<ButtonRelease-1>", self._stroke_end)
        canvas.bind("<ButtonRelease-3>", self._stroke_end)
        canvas.bind("<Motion>", self._motion)
        canvas.bind("<Leave>", self._leave)

    def _configure(self, event) -> None:
        """Размер изменился: сразу сдвигаем всё к новому центру, а перестраиваем, когда размер устоится."""
        if not self.built:
            self.width = event.width
            self.build()
            return
        shift = (event.width - self.width) // 2
        self.width = event.width
        if shift:
            self.c.move("all", shift, 0)
        if self.build_job is not None:
            self.c.after_cancel(self.build_job)
        self.build_job = self.c.after(60, lambda: self.build(fade=False))

    # ------------------------------------------------------------------ рисунки
    def _load_patterns(self) -> list[set]:
        """Читает рисунки из настроек. Первый по умолчанию это логотип."""
        saved = self.app.s["sequencer_patterns"]
        result = []
        for index in range(PATTERNS):
            cells = saved[index] if index < len(saved) else (self.logo if index == 0 else ())
            result.append({(int(c), int(r)) for c, r in cells if 0 <= int(c) < COLUMNS and 0 <= int(r) < ROWS})
        return result

    def _save_patterns(self) -> None:
        """Сохраняет рисунки в настройках."""
        self.app.s["sequencer_patterns"] = [sorted(cells) for cells in self.patterns]
        self.app.s.save()

    def _pick_pattern(self, index: int) -> None:
        """Переключает рисунок. Звук подхватит его со следующего шага."""
        self.active_pattern = index
        self.pattern = self.mixer.pattern = self.patterns[index]
        for key in self.pattern:
            self.energy[key] = 0.5
        self._paint_choices()

    # ------------------------------------------------------------------ разметка
    def _background(self) -> str:
        """Цвет фона страницы с учётом затемнения."""
        return mix(self.colors["PANEL"], "#000000", DARKEST * self.dark)

    def build(self, fade: bool = True) -> None:
        """Рисует вкладку заново. fade: тексты плавно проявляются."""
        c, t, tone = self.c, self.t, self.colors
        p = t.p
        self.build_job = None
        if self.tempo_entry:  # поле ввода это отдельный виджет: очистка холста его не удаляет
            self.tempo_entry.destroy()
            self.tempo_entry = None
        c.delete("all")
        c.configure(bg=self._background())
        self.pads, self.painted, self.fading, self.step_labels = {}, {}, [], []
        self.changing = {}
        self.fade = fade
        width, height = c.winfo_width(), c.winfo_height()
        self.width = width
        self.pad, self.gap, self.letter_gap = p(15), p(3), p(12)
        self.pitch = self.pad + self.gap
        letter_w = LETTER_COLUMNS * self.pitch - self.gap
        self.grid_w = 4 * letter_w + 3 * self.letter_gap
        cx = width // 2
        frame_x, frame_y = cx - p(390), p(4)
        self.frame_box = (frame_x, frame_y, frame_x + p(781), frame_y + p(247))
        self.x0, self.y0, title_x, title_y = self._places(self.seq_on)
        for column in range(COLUMNS):
            for row in range(ROWS):
                x, y = self._pad_xy(column, row)
                self.pads[column, row] = c.create_rectangle(x, y, x + self.pad, y + self.pad, fill=tone["GROUP"], outline="")
        self.title_item = self._text(title_x, title_y, self.title, "TEXT_BRIGHT", t.font_title)
        self.version_item = self._text(title_x, title_y + p(21), i18n.tr("Версия {version}").format(version=self.version), "TEXT_DIM", t.font)
        if self.seq_on:
            self._draw_sequencer()
        y = self.frame_box[3] + p(14)
        wrap = min(width - p(60), p(640))
        for key in ("Портативный органайзер базы плагинов FL Studio: раскладывает плагины по производителю и назначению.",
                    "Основано на FL Studio Automatic Plugin Organizer от Magabes и соавторов (лицензия MIT).",
                    "Независимый проект, не связан с Image-Line. FL Studio является товарным знаком Image-Line."):
            item = self._text(cx, y, i18n.tr(key), "TEXT_SOFT", t.font, width=wrap, anchor="n")
            y = c.bbox(item)[3] + p(8)
        y += p(10)
        signature_y = max(y + p(46), height - p(18))
        self._text(cx, signature_y, i18n.tr("Сделал то, что не смогли реализовать в официальной версии!"), "ORANGE", t.font_bold)
        import ui
        ui.IconButton(c, t, cx, y + p(14), "ic_github", self.app.open_project, self._background())
        self.author_item = c.create_text(p(10), height - p(12), text="By Arkomiko", anchor="w", fill=self._author_color(False), font=t._font(11))
        self._draw_fox(width, height)
        if fade:
            self.frame = 0
        if not self.built or fade:
            self.energy = {}
        self.built = True
        if self.visible:
            self.start()

    def _places(self, sequencer_mode: bool) -> tuple[int, int, int, int]:
        """Где стоят сетка и название: x и y сетки, x и y названия."""
        p = self.t.p
        if sequencer_mode:  # сетка сдвинута: слева темп, справа уровень и громкость
            left, top = self.frame_box[:2]
            return left + p(172), top + p(52), left + p(328), top + p(192)
        y = p(42)
        cx = self.c.winfo_width() // 2
        return cx - self.grid_w // 2, y, cx, y + ROWS * self.pitch + p(20)

    def _text(self, x, y, text, tone_key, font, **options):
        """Создаёт текст; при fade он проявится из цвета фона."""
        fill = self._background() if self.fade else self.colors[tone_key]
        item = self.c.create_text(x, y, text=text, fill=fill, font=font, **options)
        self.fading.append((item, tone_key))
        return item

    def _pad_xy(self, column: int, row: int) -> tuple[int, int]:
        """Экранные координаты ячейки."""
        return (self.x0 + column * self.pitch + (column // LETTER_COLUMNS) * (self.letter_gap - self.gap), self.y0 + row * self.pitch)

    def _pad_at(self, x: int, y: int) -> tuple[int, int] | None:
        """Какая ячейка находится в точке экрана (или None)."""
        for key in self.pads:
            px, py = self._pad_xy(*key)
            if px <= x < px + self.pad and py <= y < py + self.pad:
                return key
        return None

    # ------------------------------------------------------------------ лисичка
    def _fox_colors(self) -> tuple[str, str]:
        """Цвета контура и глаз. Берутся из темы и почти сливаются с фоном, при наведении чуть ярче."""
        back = self._background()
        line = mix(back, self.colors["TEXT_BRIGHT"], 0.30 if self.fox_hover else 0.16)
        eyes = mix(back, self.colors["ORANGE"], 0.75 if self.fox_hover else 0.28)
        return line, eyes

    def _draw_fox(self, width: int, height: int) -> None:
        """Лисичка в правом нижнем углу."""
        t = self.t
        line, eyes = self._fox_colors()
        image = t.tinted("fx_line", line)
        side = image.width()
        x0, y0 = width - t.p(8) - side, height - t.p(8) - side
        self.fox_line = self.c.create_image(x0, y0, anchor="nw", image=image)
        self.fox_eyes = self.c.create_image(x0, y0, anchor="nw", image=t.tinted("fx_eye0", eyes))
        self.fox_box = (x0, y0, x0 + side, y0 + side)

    def _paint_fox(self, frame: int = 0) -> None:
        """Обновляет цвета лисички и положение век."""
        line, eyes = self._fox_colors()
        self.c.itemconfigure(self.fox_line, image=self.t.tinted("fx_line", line))
        self.c.itemconfigure(self.fox_eyes, image=self.t.tinted(f"fx_eye{frame}", eyes))

    def _set_fox_hover(self, hover: bool) -> None:
        """Наведение: лисичка становится чуть ярче и машет глазками."""
        if hover == self.fox_hover:
            return
        self.fox_hover = hover
        self._paint_fox()
        if hover:
            def step(share):
                self._paint_fox(BLINK_FRAMES[min(len(BLINK_FRAMES) - 1, int(share * len(BLINK_FRAMES)))])
            self.t.motion.run("fox_blink", 560, step, lambda: self._paint_fox())

    # ------------------------------------------------------------------ превращение
    def toggle_sequencer(self) -> None:
        """Клик по лисичке: превращение в секвенсор или возврат к логотипу."""
        if self.busy:
            return
        self.stop()
        if self.seq_on:
            self._close_sequencer()
        else:
            self.busy = True
            self._trace_frame()

    def _trace_frame(self) -> None:
        """Шаг 1: линия обводит будущую рамку, начиная от лисички."""
        c, p = self.c, self.t.p
        x0, y0, x1, y1 = self.frame_box
        path = [(x1, y1), (x0, y1), (x0, y0), (x1, y0), (x1, y1)]
        lengths = [abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(path, path[1:])]
        total = sum(lengths)
        line = c.create_line(*path[0], *path[0], fill=self.colors["ORANGE"], width=p(2))

        def step(share):
            left = total * (1 - (1 - share) ** 2)  # линия плавно замедляется к концу
            points = [path[0]]
            for corner, length in zip(path[1:], lengths):
                if left >= length:
                    points.append(corner)
                    left -= length
                else:
                    a = points[-1]
                    points.append((a[0] + (corner[0] - a[0]) * left / length, a[1] + (corner[1] - a[1]) * left / length))
                    break
            c.coords(line, *[value for point in points for value in point])

        self.t.motion.run("about_trace", TRACE_MS, step, self._darken)

    def _darken(self) -> None:
        """Шаг 2: фон страницы темнеет, затем логотип едет на своё место в секвенсоре (шаг 3)."""
        self._animate_dark(1.0, DARKEN_MS, lambda: self._glide(self._places(False), self._places(True), self._become_sequencer))

    def _animate_dark(self, target: float, ms: int, done) -> None:
        """Плавно меняет затемнение фона."""
        start = self.dark

        def step(share):
            self.dark = start + (target - start) * share
            self.c.configure(bg=self._background())

        self.t.motion.run("about_dark", ms, step, done)

    def _glide(self, start: tuple, end: tuple, done=None) -> None:
        """Плавно переносит сетку и название из одного места в другое, к концу замедляясь."""
        def step(share):
            eased = 1 - (1 - share) ** 3
            self._place_logo(*(round(a + (b - a) * eased) for a, b in zip(start, end)))
        self.t.motion.run("about_glide", GLIDE_MS, step, done)

    def _place_logo(self, x: int, y: int, title_x: int, title_y: int) -> None:
        """Ставит ячейки и название в заданные точки."""
        self.x0, self.y0 = x, y
        for key, item in self.pads.items():
            pad_x, pad_y = self._pad_xy(*key)
            self.c.coords(item, pad_x, pad_y, pad_x + self.pad, pad_y + self.pad)
        self.c.coords(self.title_item, title_x, title_y)
        self.c.coords(self.version_item, title_x, title_y + self.t.p(21))

    def _become_sequencer(self) -> None:
        """Шаг 4: логотип становится секвенсором, по ячейкам проходит волна, панели проявляются."""
        x0, y0, x1, y1 = self.frame_box
        root_x, root_y = self.c.winfo_rootx(), self.c.winfo_rooty()
        self.app.fade_rect(root_x + x0, root_y + y0, x1 - x0, y1 - y0, self._background())
        self.seq_on = True
        self.busy = False
        self.sweeping = True
        self.frame = 0
        self.build(fade=False)

    def _close_sequencer(self) -> None:
        """Обратно к логотипу: панели гаснут, логотип едет на середину, фон светлеет."""
        x0, y0, x1, y1 = self.frame_box
        self.app.fade_rect(self.c.winfo_rootx() + x0, self.c.winfo_rooty() + y0, x1 - x0, y1 - y0, self._background())
        start = self._places(True)
        self.seq_on = False
        self.busy = True
        self.build(fade=False)
        self._place_logo(*start)

        def done():
            self.busy = False
            self.build(fade=False)
        self._animate_dark(0.0, DARKEN_MS, None)
        self._glide(start, self._places(False), done)

    # ------------------------------------------------------------------ секвенсор
    def _draw_sequencer(self) -> None:
        """Рамка секвенсора и всё, что в ней. Числа в at() это координаты внутри рамки, как в макете."""
        import settings_page
        import ui
        c, t, tone = self.c, self.t, self.colors
        p = t.p
        tr = i18n.tr
        back = self._background()
        left, top = self.frame_box[:2]

        def at(x, y):
            return left + p(x), top + p(y)

        t.soft_frame(c, self.frame_box, tone["ORANGE"], back, p(2), ())
        self.tooltip = self._text(*at(328, 15), "", "ORANGE", t.font)  # название элемента под мышью
        for column in range(COLUMNS):
            x, _y = self._pad_xy(column, 0)
            self.step_labels.append(c.create_text(x + self.pad // 2, self.y0 - p(10), text=str(column + 1), fill=tone["TEXT_DIM"], font=t.font))
        for row, label in enumerate(ROW_LABELS):
            _x, y = self._pad_xy(0, row)
            item = c.create_text(self.x0 - p(3), y + self.pad // 2, text=label, anchor="e", fill=tone["TEXT_DIM"], font=t.font)
            c.tag_bind(item, "<Enter>", lambda e, r=row: self._show_tip(self._row_tip(r)))
            c.tag_bind(item, "<Leave>", lambda e: self._show_tip(""))
        # Индикатор уровня и громкость справа от сетки.
        meter_x, meter_y = at(492, 52)
        self.meter = (meter_x, meter_y, meter_x + p(6), meter_y + p(123))
        c.create_rectangle(*self.meter, fill=tone["BOX"], outline=tone["BOX_LINE"])
        self.meter_fill = c.create_rectangle(meter_x + 1, self.meter[3], self.meter[2], self.meter[3], fill=tone["ORANGE"], outline="")

        self.pattern_chips = {}
        for index in range(PATTERNS):
            x, y = at(15 + index * 16, 26)
            self.pattern_chips[index] = self._chip(x, y - p(10), p(16), p(20), str(index + 1), tr("Паттерн {number}").format(number=index + 1), lambda v=index: self._pick_pattern(v))
        self.play_btn = self._icon_button(*at(31, 55), "ic_play_big", tr("Играть"), self.play)
        self.stop_btn = self._icon_button(*at(69, 55), "ic_stop_big", tr("Стоп"), self.stop)
        self._paint_transport()

        # Темп: ползунок и крупное число, которое можно ввести вручную.
        self._caption(*at(15, 77), tr("Темп"))
        self.tempo_slider = settings_page.Slider(c, t, *at(15, 94), p(120), 60, 180, self.mixer.bpm, "", lambda v: None, self._set_bpm, 5, back)
        check = c.register(lambda text: text == "" or (text.isdigit() and len(text) <= 3))
        entry = self.tempo_entry = tk.Entry(c, bd=0, highlightthickness=0, bg=back, fg=tone["TEXT_BRIGHT"], insertbackground=tone["ORANGE"], font=t._font(22),
                                            selectbackground=tone["SELECT"], validate="key", validatecommand=(check, "%P"))
        entry.insert(0, str(self.mixer.bpm))
        c.create_window(*at(15, 124), anchor="w", width=p(56), window=entry)
        c.create_line(*at(15, 140), *at(71, 140), fill=mix(back, tone["TEXT"], 0.3))
        c.create_text(*at(77, 130), text="BPM", anchor="w", fill=tone["TEXT_DIM"], font=t.font)
        entry.bind("<Return>", self._commit_tempo)
        entry.bind("<FocusOut>", self._commit_tempo)

        # Громкость: значок выключает звук, ползунок вертикальный. Число видно в подсказке.
        self.mute_btn = ui.IconButton(c, t, *at(513, 57), "ic_sound", self._toggle_mute, back)
        c.tag_bind(self.mute_btn.tag, "<Enter>", lambda e: self._show_tip(self._volume_tip()), add="+")
        c.tag_bind(self.mute_btn.tag, "<Leave>", lambda e: self._show_tip(""), add="+")
        self._paint_mute()
        x, y = at(513, 72)
        volume = VerticalSlider(c, tone, x, y, top + p(175), round(self.mixer.volume * 100), self._set_volume, back, p)
        c.tag_bind(volume.tag, "<Enter>", lambda e: self._show_tip(self._volume_tip()), add="+")
        c.tag_bind(volume.tag, "<Leave>", lambda e: self._show_tip(""), add="+")

        # Звук и лад: значок, двоеточие и четыре равных столбца до края рамки.
        self._mark(*at(540, 46), "ic_sound", tr("Звук"), back)
        self.timbre_btns = {}
        for index, (key, name) in enumerate(sequencer.TIMBRES.items()):
            self.timbre_btns[key] = self._icon_button(*at(574 + index * 58, 46), "ic_" + key, tr(name), lambda v=key: self._pick("timbre", v))
        self._mark(*at(540, 76), "ic_scale", tr("Лад"), back)
        self.scale_chips = {}
        for index, (key, label) in enumerate(SCALE_LABELS.items()):
            x, y = at(574 + index * 58, 76)
            self.scale_chips[key] = self._chip(x - p(19), y - p(12), p(38), p(24), label, tr(sequencer.SCALES[key][0]), lambda v=key: self._pick("scale", v))

        # Тональность: буквы в рамке, под ними пианино с нажатыми клавишами.
        x, y = at(531, 95)
        cell_w, cell_h = p(39), p(21)
        t.soft_frame(c, (x, y, x + 6 * cell_w + 2, y + 2 * cell_h + 2), mix(back, tone["TEXT"], 0.3), back, 1, ())
        self.key_chips = {}
        for index, name in enumerate(sequencer.KEYS):
            self.key_chips[index] = self._chip(x + 1 + (index % 6) * cell_w, y + 1 + (index // 6) * cell_h, cell_w, cell_h, name,
                                               f"{tr('Тональность')}: {name}", lambda v=index: self._pick("key", v))
        self._draw_piano(x, y + 2 * cell_h + p(6), 6 * cell_w + 2, p(70))

        # Экспорт: слово, двоеточие и два значка.
        x, y = at(15, 207)
        word = tr("Экспортировать")
        c.create_text(x, y, text=word, anchor="w", fill=tone["TEXT_SOFT"], font=t.font)
        x += t.font.measure(word) + p(5)
        c.create_text(x, y, text=":", fill=tone["TEXT_DIM"], font=t.font)
        self._icon_button(x + p(17), y, "ic_wav", tr("Экспорт WAV"), self._export_wav)
        self._icon_button(x + p(41), y, "ic_midi", tr("Экспорт MIDI"), self._export_midi)
        self._paint_choices()

    def _draw_piano(self, x: int, y: int, width: int, height: int) -> None:
        """Две октавы от C. Клавиши перекрашивает _paint_choices. Названия нот видны в подсказке."""
        c, p = self.c, self.t.p
        back = self._background()
        white_w = width / 14
        self.piano = {}
        tag = f"piano{id(self)}"
        for octave in range(2):
            for index, note in enumerate(WHITE_KEYS):
                left = x + (index + octave * 7) * white_w
                self.piano[note + octave * 12] = c.create_rectangle(left, y, left + white_w, y + height, outline=back, tags=tag)
        for octave in range(2):
            for note, place in BLACK_KEYS.items():
                middle = x + (place + octave * 7) * white_w
                self.piano[note + octave * 12] = c.create_rectangle(middle - p(5), y, middle + p(5), y + height * 0.62, outline=back, tags=tag)
        c.tag_bind(tag, "<Enter>", lambda e: self._show_tip("  ".join(self._scale_notes())))
        c.tag_bind(tag, "<Leave>", lambda e: self._show_tip(""))

    def _scale_notes(self) -> list[str]:
        """Названия нот текущего лада."""
        return [sequencer.KEYS[(self.mixer.key + step) % 12] for step in sequencer.SCALES[self.mixer.scale][1]]

    def _mark(self, x, y, icon, tooltip, back) -> None:
        """Значок-подпись ряда и двоеточие после него."""
        c = self.c
        image = c.create_image(x, y, image=self.t.tinted(icon, self.colors["TEXT_SOFT"], back))
        c.tag_bind(image, "<Enter>", lambda e: self._show_tip(tooltip))
        c.tag_bind(image, "<Leave>", lambda e: self._show_tip(""))
        c.create_text(x + self.t.p(13), y, text=":", fill=self.colors["TEXT_DIM"], font=self.t.font)

    def _chip(self, x, y, width, height, label, tooltip, pick) -> int:
        """Надпись без рамки, которую можно выбрать. Подсвечивается при наведении."""
        c = self.c
        tag = f"chip{x}_{y}"
        c.create_rectangle(x, y, x + width, y + height, fill=self._background(), outline="", tags=tag)
        item = c.create_text(x + width // 2, y + height // 2, text=label, fill=self.colors["TEXT_BRIGHT"], font=self.t.font, tags=tag)

        def enter(_event):
            c.itemconfigure(item, fill=self.colors["ORANGE"])
            self._show_tip(tooltip)

        def leave(_event):
            self._paint_choices()
            self._show_tip("")
        c.tag_bind(tag, "<Enter>", enter)
        c.tag_bind(tag, "<Leave>", leave)
        c.tag_bind(tag, "<ButtonRelease-1>", lambda e: pick())
        return item

    def _pick(self, setting: str, value) -> None:
        """Выбор тембра, лада или тональности."""
        setattr(self.mixer, setting, value)
        self._paint_choices()

    def _paint_choices(self) -> None:
        """Подсвечивает выбранное и нажимает на пианино ноты текущего лада."""
        tone, mixer = self.colors, self.mixer
        for key, item in self.pattern_chips.items():
            self.c.itemconfigure(item, fill=tone["ORANGE" if key == self.active_pattern else "TEXT_BRIGHT" if self.patterns[key] else "TEXT_DIM"])
        for key, button in self.timbre_btns.items():
            button.set_active(key == mixer.timbre)
        for key, item in self.scale_chips.items():
            self.c.itemconfigure(item, fill=tone["ORANGE" if key == mixer.scale else "TEXT_BRIGHT"])
        for key, item in self.key_chips.items():
            self.c.itemconfigure(item, fill=tone["ORANGE" if key == mixer.key else "TEXT_BRIGHT"])
        used = {mixer.key + step for step in sequencer.SCALES[mixer.scale][1]}
        for note, item in self.piano.items():
            black = note % 12 in BLACK_KEYS
            if note == mixer.key:  # основная нота насыщенная, остальные светлее
                color = tone["ORANGE"]
            elif note in used:
                color = mix(tone["ORANGE"], "#FFFFFF", 0.6)
            else:
                color = tone["BTN_BORDER"] if black else mix(self._background(), tone["TEXT_BRIGHT"], 0.8)
            self.c.itemconfigure(item, fill=color)

    def _show_tip(self, text: str) -> None:
        """Название элемента над сеткой."""
        self.c.itemconfigure(self.tooltip, text=text)

    def _row_tip(self, row: int) -> str:
        """Подсказка строки: нота мелодии или название барабана."""
        if row in DRUM_TIPS:
            return DRUM_TIPS[row]
        return sequencer.KEYS[sequencer.melody_note(row, self.mixer.key, self.mixer.scale) % 12]

    def _volume_tip(self) -> str:
        """Подсказка громкости с текущим числом."""
        return f"{i18n.tr('Громкость')}: {round(self.mixer.volume * 100)} %"

    def _icon_button(self, x, y, icon, tooltip, command):
        """Значок. Его название появляется над сеткой, пока мышь над ним."""
        import ui
        c = self.c
        button = ui.IconButton(c, self.t, x, y, icon, command, self._background())
        c.tag_bind(button.tag, "<Enter>", lambda e: c.itemconfigure(self.tooltip, text=tooltip), add="+")
        c.tag_bind(button.tag, "<Leave>", lambda e: c.itemconfigure(self.tooltip, text=""), add="+")
        return button

    def _paint_transport(self) -> None:
        """Состояние значков «играть» и «стоп»: пока звук идёт, «играть» горит."""
        playing = self.player is not None
        self.play_btn.set_active(playing)
        self.play_btn.set_enabled(not playing)
        self.stop_btn.set_enabled(playing)

    def _caption(self, x: int, y: int, text: str) -> None:
        """Маленькая подпись на панели."""
        self.c.create_text(x, y, text=text, anchor="w", fill=self.colors["TEXT_SOFT"], font=self.t.font)

    def _set_bpm(self, value: int) -> None:
        """Ползунок темпа: новое число сразу видно в поле."""
        self.mixer.bpm = value
        self.tempo_entry.delete(0, "end")
        self.tempo_entry.insert(0, str(value))

    def _commit_tempo(self, event=None) -> None:
        """Темп, введённый вручную. Enter или уход из поля подтверждает, значение ограничено 60-180."""
        text = self.tempo_entry.get()
        value = max(60, min(180, int(text))) if text else self.mixer.bpm
        self.tempo_slider.value = value
        self.tempo_slider._paint()
        self._set_bpm(value)
        if event is not None and event.keysym == "Return":
            self.c.focus_set()

    def _set_volume(self, value: int) -> None:
        """Меняет громкость."""
        self.mixer.volume = value / 100
        self._show_tip(self._volume_tip())

    def _toggle_mute(self) -> None:
        """Включает или выключает звук."""
        self.mixer.muted = not self.mixer.muted
        self._paint_mute()

    def _paint_mute(self) -> None:
        """Значок звука: перечёркнутый и подсвеченный, пока звук выключен."""
        self.mute_btn.set_icon("ic_mute" if self.mixer.muted else "ic_sound")
        self.mute_btn.set_active(self.mixer.muted)

    def play(self) -> None:
        """Запускает рисунок по кругу."""
        if self.player is None:
            self.mixer.tail = []
            self.player = sequencer.Player(self.mixer)
            self._paint_transport()

    def stop(self) -> None:
        """Останавливает звук."""
        if self.player is not None:
            self.player.stop()
            self.player = None
            self.level = 0.0
            if self.seq_on and self.c.winfo_exists():
                self._paint_transport()

    def _export(self, extension: str, data: bytes) -> None:
        """Сохраняет рисунок в выбранный файл."""
        path = filedialog.asksaveasfilename(parent=self.app.root, defaultextension=extension, initialfile="FODB" + extension,
                                            filetypes=[(extension[1:].upper(), "*" + extension)])
        if path:
            try:
                with open(path, "wb") as f:
                    f.write(data)
            except OSError as exc:
                self.app.show_error(str(exc))

    def _export_wav(self) -> None:
        """Экспорт в WAV."""
        m = self.mixer
        self._export(".wav", sequencer.wav_bytes(self.pattern, m.bpm, m.key, m.scale, m.timbre))

    def _export_midi(self) -> None:
        """Экспорт в MIDI."""
        m = self.mixer
        self._export(".mid", sequencer.midi_bytes(self.pattern, m.bpm, m.key, m.scale))

    # ------------------------------------------------------------------ мышь
    @staticmethod
    def _inside(box, event) -> bool:
        """Попала ли мышь в прямоугольник."""
        x0, y0, x1, y1 = box
        return x0 <= event.x <= x1 and y0 <= event.y <= y1

    def _motion(self, event) -> None:
        """Подсветка и курсор-рука там, где можно нажать."""
        self.hover = self._pad_at(event.x, event.y) if self.seq_on else None
        on_version = self._inside(self.c.bbox(self.version_item) or (0, 0, 0, 0), event)
        on_fox = self._inside(self.fox_box, event)
        self._set_fox_hover(on_fox)
        on_author = self._inside(self.c.bbox(self.author_item) or (0, 0, 0, 0), event)
        self.c.itemconfigure(self.author_item, fill=self._author_color(on_author))
        link = on_version or on_fox or self.hover or on_author
        self.c.configure(cursor="hand2" if link else "")
        self.c.itemconfigure(self.version_item, fill=self.colors["ORANGE" if on_version else "TEXT_DIM"])

    def _author_color(self, hover: bool) -> str:
        """Цвет подписи автора: едва заметный, при наведении ярче."""
        return self.colors["ORANGE"] if hover else mix(self._background(), self.colors["TEXT"], 0.3)

    def _leave(self, _event) -> None:
        """Мышь ушла со страницы."""
        self.hover = None
        self._set_fox_hover(False)

    def _click(self, event) -> None:
        """Левый клик: ссылка, лисичка или ячейка секвенсора. Логотип на клики не реагирует."""
        self.c.focus_set()  # щелчок мимо поля темпа подтверждает введённое число
        if self._inside(self.c.bbox(self.version_item) or (0, 0, 0, 0), event):
            self.app.open_releases()
        elif self._inside(self.c.bbox(self.author_item) or (0, 0, 0, 0), event):
            self.app._open(AUTHOR_URL)
        elif self._inside(self.fox_box, event):
            self.toggle_sequencer()
        else:
            self._stroke_start(event, True)

    def _erase_press(self, event) -> None:
        """Правая кнопка: стирает ячейку и начинает стирание протягиванием."""
        self._stroke_start(event, False)

    def _stroke_start(self, event, add: bool) -> None:
        """Левая кнопка ставит ячейки, правая стирает. Начать можно только с ячейки сетки."""
        if not self.seq_on or self.busy:
            return
        key = self._pad_at(event.x, event.y)
        if key is not None:
            self.stroke, self.stroke_pad = add, key
            self._apply_stroke(key)

    def _stroke_motion(self, event) -> None:
        """Кнопка зажата: обрабатывает все ячейки на пути мыши, чтобы быстрое движение не оставляло дыр."""
        if self.stroke is None:
            return
        key = self._pad_at(event.x, event.y)
        if key is None or key == self.stroke_pad:
            return
        column, row = self.stroke_pad
        steps = max(abs(key[0] - column), abs(key[1] - row))
        for step in range(1, steps + 1):
            self._apply_stroke((column + round((key[0] - column) * step / steps), row + round((key[1] - row) * step / steps)))
        self.stroke_pad = key

    def _stroke_end(self, _event) -> None:
        """Кнопка отпущена: рисунок сохраняется."""
        if self.stroke is not None:
            self._save_patterns()
            if self.seq_on:
                self._paint_choices()
        self.stroke = self.stroke_pad = None

    def _apply_stroke(self, key: tuple[int, int]) -> None:
        """Ставит или стирает одну ячейку."""
        if (key in self.pattern) != self.stroke:
            if self.stroke:
                self.pattern.add(key)
            else:
                self.pattern.discard(key)
            self._ripple(key)
            self._begin_change(key, self.stroke)

    def _begin_change(self, key: tuple[int, int], added: bool) -> None:
        """Запускает анимацию ячейки: поверх неё появляется временный квадратик."""
        if key in self.changing:
            self.c.delete(self.changing[key][0])
        item = self.c.create_rectangle(0, 0, 0, 0, fill=self._lit_color(key), outline="", state="disabled")
        self.changing[key] = [item, 0, added]
        self._step_change(key)

    def _step_change(self, key: tuple[int, int]) -> None:
        """Один кадр анимации ячейки. Когда кадры кончились, остаётся обычная ячейка."""
        item, frame, added = self.changing[key]
        steps = POP_SIZES if added else DISSOLVE_STEPS
        if frame >= len(steps):
            self.c.delete(item)
            del self.changing[key]
            return
        x, y = self._pad_xy(*key)
        if added:
            margin = self.pad * (1 - POP_SIZES[frame]) / 2
            self.c.coords(item, x + margin, y + margin, x + self.pad - margin, y + self.pad - margin)
        else:
            self.c.coords(item, x, y, x + self.pad, y + self.pad)
            self.c.itemconfigure(item, stipple=DISSOLVE_STEPS[frame])
        self.changing[key][1] = frame + 1

    def _lit_color(self, key: tuple[int, int]) -> str:
        """Цвет зажжённой ячейки: барабаны светлее мелодии."""
        lit = self.colors["ORANGE"]
        return mix(lit, self.colors["TEXT_BRIGHT"], 0.45) if self.seq_on and key[1] >= sequencer.HAT else lit

    def _ripple(self, center: tuple[int, int]) -> None:
        """Волна подсветки вокруг нажатой ячейки."""
        for key in self.pads:
            distance = math.hypot(key[0] - center[0], key[1] - center[1])
            if distance < 3.5:
                self.energy[key] = max(self.energy.get(key, 0.0), 1.0 - distance / 3.5)

    # ------------------------------------------------------------------ анимация
    def show(self) -> None:
        """Вкладка открыта: запускаем анимацию."""
        self.visible = True
        self.start()

    def hide(self) -> None:
        """Вкладка скрыта: звук выключается, анимация останавливается сама."""
        self.visible = False
        self.stop()

    def start(self) -> None:
        """Запускает таймер анимации, если он ещё не идёт."""
        if not self.running and self.pads:
            self.running = True
            self._tick()

    def _tick(self) -> None:
        """Один кадр анимации."""
        if not self.visible or not self.c.winfo_exists():
            self.running = False
            return
        self._advance()
        self._paint()
        self.frame += 1
        self.c.after(FRAME_MS, self._tick)

    def _advance(self) -> None:
        """Считает новое состояние кадра: затухание, тексты, волна логотипа, шаг секвенсора."""
        for key in list(self.changing):
            self._step_change(key)
        for key in list(self.energy):
            self.energy[key] *= 0.84
            if self.energy[key] < 0.02:
                del self.energy[key]
        if self.fade and self.frame <= INTRO_FRAMES:
            share = self.frame / INTRO_FRAMES
            back = self._background()
            for item, tone_key in self.fading:
                self.c.itemconfigure(item, fill=mix(back, self.colors[tone_key], share))
        phase = self.frame % CYCLE_FRAMES
        if self.seq_on and self.sweeping and phase > INTRO_FRAMES:
            self.sweeping = False  # при превращении волна проходит один раз
        if (not self.seq_on or self.sweeping) and phase <= INTRO_FRAMES:
            head = phase * COLUMNS / (INTRO_FRAMES * 0.7)
            for key in self.pads:
                if abs(key[0] - head) < 0.8:
                    self.energy[key] = 1.0
        if self.player is not None:
            step, level = self.player.position()
            self.level = max(level, self.level * 0.8)
            for row in range(ROWS):
                self.energy[step, row] = 1.0 if (step, row) in self.pattern else max(self.energy.get((step, row), 0.0), 0.6)
            for index, item in enumerate(self.step_labels):
                self.c.itemconfigure(item, fill=self.colors["ORANGE" if index == step else "TEXT_DIM"])
        else:
            self.level *= 0.8
            for item in self.step_labels:
                self.c.itemconfigure(item, fill=self.colors["TEXT_DIM"])
        if self.seq_on:
            x0, y0, x1, y1 = self.meter
            self.c.coords(self.meter_fill, x0 + 1, y1 - (y1 - y0) * min(1.0, self.level), x1, y1)

    def _reveal(self) -> float:
        """Насколько сейчас зажжён логотип: зажигается, горит, плавно гаснет перед новым кругом."""
        if self.seq_on or self.busy:
            return 1.0
        phase = self.frame % CYCLE_FRAMES
        if phase < INTRO_FRAMES:
            return phase / INTRO_FRAMES
        if phase > CYCLE_FRAMES - FADE_FRAMES:
            return (CYCLE_FRAMES - phase) / FADE_FRAMES
        return 1.0

    def _paint(self) -> None:
        """Красит только те ячейки, цвет которых изменился."""
        tone = self.colors
        lit, dim = tone["ORANGE"], tone["GROUP"]
        hot = mix(lit, "#FFFFFF", 0.6)
        idle = mix(dim, tone["TEXT"], 0.32)
        reveal = self._reveal()
        pattern = self.pattern if self.seq_on else self.logo
        for key, item in self.pads.items():
            on = key in pattern and key not in self.changing  # в анимации ячейку рисует временный квадратик
            shade = self._lit_color(key)
            base = (mix(dim, shade, reveal) if reveal < 1 else shade) if on else dim
            energy = self.energy.get(key, 0.0)
            if key == self.hover:
                energy = max(energy, 0.45)
            color = mix(base, hot if on else idle, min(1.0, energy)) if energy else base
            if self.painted.get(item) != color:
                self.c.itemconfigure(item, fill=color)
                self.painted[item] = color
