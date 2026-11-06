"""Вкладка «О программе»: логотип FODB, который работает как пошаговый секвенсор.

Каждая ячейка нажимается. Первый клик запускает секвенсор: столбец это шаг, строка это нота,
горящие ячейки становятся мелодией. Перерисовываются только изменившиеся ячейки,
а анимация идёт, только пока вкладка видна.
"""
from __future__ import annotations

import array
import io
import math
import queue
import threading
import wave

import i18n
from theme import mix

try:
    import winsound
except ImportError:  # без звука вкладка тоже работает
    winsound = None

FRAME_MS = 33
STEP_MS = 165
LETTERS = {
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
}
ROWS, LETTER_COLUMNS = 7, 5
COLUMNS = 4 * LETTER_COLUMNS
# Минорная пентатоника, верхняя строка самая высокая: любой рисунок звучит складно.
NOTES_HZ = (880.0, 784.0, 659.25, 587.33, 523.25, 440.0, 392.0)
SAMPLE_RATE = 22050
INTRO_FRAMES = 34


class Sequencer:
    """Играет по одному шагу в фоновом потоке. Опоздавший шаг пропускается, очереди нет."""

    def __init__(self):
        """Готовит ноты и запускает поток воспроизведения."""
        self.pending: queue.Queue = queue.Queue(maxsize=1)
        self.cache: dict[int, bytes] = {}
        self.voices = [self._voice(hz) for hz in NOTES_HZ]
        threading.Thread(target=self._run, daemon=True).start()

    @staticmethod
    def _voice(hz: float) -> list[float]:
        """Одна затухающая нота: синусоида заданной частоты."""
        count = int(SAMPLE_RATE * STEP_MS / 1000 * 1.1)
        return [math.sin(2 * math.pi * hz * i / SAMPLE_RATE) * math.exp(-i / (count * 0.28)) for i in range(count)]

    def _render(self, mask: int) -> bytes:
        """Смешивает ноты шага в WAV. mask: бит на каждую строку."""
        chosen = [voice for row, voice in enumerate(self.voices) if mask >> row & 1]
        gain = 9000 / max(1, len(chosen)) ** 0.7
        samples = array.array("h", (int(sum(values) * gain) for values in zip(*chosen)))
        out = io.BytesIO()
        with wave.open(out, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(samples.tobytes())
        return out.getvalue()

    def play(self, mask: int) -> None:
        """Ставит шаг на воспроизведение, если поток свободен."""
        if winsound is None or not mask:
            return
        try:
            self.pending.put_nowait(mask)
        except queue.Full:
            pass

    def _run(self) -> None:
        """Цикл потока: берёт шаг и проигрывает его."""
        while True:
            mask = self.pending.get()
            data = self.cache.get(mask)
            if data is None:
                data = self.cache[mask] = self._render(mask)
            try:
                winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
            except (RuntimeError, OSError):
                return


class AboutPage:
    """Рисует вкладку и управляет её анимацией."""

    def __init__(self, canvas, theme, colors: dict, title: str, version: str, open_project):
        """Запоминает холст и подключает события мыши."""
        self.c, self.t, self.colors = canvas, theme, colors
        self.title, self.version, self.open_project = title, version, open_project
        self.visible = False
        self.running = False
        self.sequencer: Sequencer | None = None
        self.awake = False
        self.frame = 0
        self.step = 0
        self.next_step_frame = 0
        self.energy: dict[tuple[int, int], float] = {}
        self.pattern = self._logo()
        self.pads: dict[tuple[int, int], int] = {}
        self.painted: dict[int, str] = {}
        self.fading: list[tuple[int, str]] = []
        self.hover = None
        canvas.bind("<Configure>", lambda e: self.build())
        canvas.bind("<Button-1>", self._click)
        canvas.bind("<Motion>", self._motion)
        canvas.bind("<Leave>", lambda e: self._set_hover(None))

    @staticmethod
    def _logo() -> set[tuple[int, int]]:
        """Набор ячеек (столбец, строка), из которых складываются буквы FODB."""
        lit = set()
        for index, letter in enumerate("FODB"):
            for row, pattern in enumerate(LETTERS[letter]):
                lit.update((index * LETTER_COLUMNS + col, row) for col, value in enumerate(pattern) if value == "#")
        return lit

    # ------------------------------------------------------------------ разметка
    def build(self) -> None:
        """Рисует вкладку заново: ячейки, тексты, кнопку и подпись."""
        c, t, tone = self.c, self.t, self.colors
        p = t.p
        c.delete("all")
        self.pads, self.painted = {}, {}
        width = c.winfo_width()
        self.pad, self.gap, self.letter_gap = p(15), p(3), p(12)
        self.pitch = self.pad + self.gap
        letter_w = LETTER_COLUMNS * self.pitch - self.gap
        self.x0 = (width - (4 * letter_w + 3 * self.letter_gap)) // 2
        self.y0 = p(42)
        for column in range(COLUMNS):
            for row in range(ROWS):
                x, y = self._pad_xy(column, row)
                self.pads[column, row] = c.create_rectangle(x, y, x + self.pad, y + self.pad, fill=tone["GROUP"], outline="")
        cx = width // 2
        y = self.y0 + ROWS * self.pitch + p(20)
        self.fading = []
        self._text(cx, y, self.title, "TEXT_BRIGHT", t.font_title)
        self.status = self._text(cx, y + p(22), i18n.tr("Версия {version}").format(version=self.version), "TEXT_DIM", t.font)
        y += p(52)
        wrap = min(width - p(60), p(640))
        for key in ("Портативный органайзер базы плагинов FL Studio: раскладывает плагины по производителю и назначению.",
                    "Основано на FL Studio Automatic Plugin Organizer от Magabes и соавторов (лицензия MIT).",
                    "Независимый проект, не связан с Image-Line. FL Studio является товарным знаком Image-Line."):
            item = self._text(cx, y, i18n.tr(key), "TEXT_SOFT", t.font, width=wrap, anchor="n")
            y = c.bbox(item)[3] + p(8)
        y += p(10)
        signature_y = max(y + p(46), c.winfo_height() - p(18))
        self._text(cx, signature_y, i18n.tr("Сделал то, что не смогли реализовать в официальной версии!"), "ORANGE", t.font_bold)
        self.button_box = (cx - p(90), y, cx + p(90), y + p(28))
        self.link_face = c.create_image(cx - p(90), y, anchor="nw", image=t.gradient(p(180), p(28), tone["BTN_TOP"], tone["BTN_BOTTOM"], tone["BTN_BORDER"]))
        self.link_text = self._text(cx, y + p(14), i18n.tr("Страница проекта"), "TEXT_SOFT", t.font)
        self.frame = 0
        self.energy = {}
        if self.visible:
            self.start()

    def _text(self, x, y, text, tone_key, font, **options):
        """Создаёт текст, который плавно проявится при открытии вкладки."""
        item = self.c.create_text(x, y, text=text, fill=self.colors["PANEL"], font=font, **options)
        self.fading.append((item, tone_key))
        return item

    def _pad_xy(self, column: int, row: int) -> tuple[int, int]:
        """Экранные координаты ячейки."""
        return (self.x0 + column * self.pitch + (column // LETTER_COLUMNS) * (self.letter_gap - self.gap), self.y0 + row * self.pitch)

    def _pad_at(self, x: int, y: int) -> tuple[int, int] | None:
        """Какая ячейка находится в точке экрана (или None)."""
        for key, (px, py) in ((k, self._pad_xy(*k)) for k in self.pads):
            if px <= x < px + self.pad and py <= y < py + self.pad:
                return key
        return None

    # ------------------------------------------------------------------ мышь
    def _motion(self, event) -> None:
        """Подсветка ячейки и курсор-рука при наведении."""
        self._set_hover(self._pad_at(event.x, event.y))
        x0, y0, x1, y1 = getattr(self, "button_box", (0, 0, 0, 0))
        on_link = x0 <= event.x <= x1 and y0 <= event.y <= y1
        self.c.configure(cursor="hand2" if self.hover or on_link else "")

    def _set_hover(self, key) -> None:
        """Запоминает ячейку под курсором."""
        self.hover = key

    def _click(self, event) -> None:
        """Клик: переключает ячейку или открывает страницу проекта."""
        x0, y0, x1, y1 = self.button_box
        if x0 <= event.x <= x1 and y0 <= event.y <= y1:
            self.open_project()
            return
        key = self._pad_at(event.x, event.y)
        if key is None:
            return
        self.pattern.symmetric_difference_update({key})
        self._ripple(key)
        if not self.awake:
            self.awake = True
            self.sequencer = self.sequencer or Sequencer()
            self.next_step_frame = self.frame
            self.c.itemconfigure(self.status, text=i18n.tr("Расставь всё по полочкам!"), fill=self.colors["ORANGE"])

    def _ripple(self, center: tuple[int, int]) -> None:
        """Волна подсветки вокруг нажатой ячейки."""
        for (column, row) in self.pads:
            distance = math.hypot(column - center[0], row - center[1])
            if distance < 3.5:
                key = (column, row)
                self.energy[key] = max(self.energy.get(key, 0.0), 1.0 - distance / 3.5)

    # ------------------------------------------------------------------ анимация
    def show(self) -> None:
        """Вкладка открыта: запускаем анимацию."""
        self.visible = True
        self.start()

    def hide(self) -> None:
        """Вкладка скрыта: анимация остановится сама."""
        self.visible = False

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
        """Считает новое состояние кадра: затухание, вступление, шаг секвенсора."""
        for key in list(self.energy):
            self.energy[key] *= 0.84
            if self.energy[key] < 0.02:
                del self.energy[key]
        if self.frame <= INTRO_FRAMES:
            head = self.frame * COLUMNS / (INTRO_FRAMES * 0.7)
            for key in self.pads:
                if abs(key[0] - head) < 0.8:
                    self.energy[key] = 1.0
            t = self.frame / INTRO_FRAMES
            for item, tone_key in self.fading:
                self.c.itemconfigure(item, fill=mix(self.colors["PANEL"], self.colors[tone_key], t))
            if self.frame == INTRO_FRAMES and self.awake:
                self.c.itemconfigure(self.status, fill=self.colors["ORANGE"])
        elif self.awake and self.frame >= self.next_step_frame:
            column = self.step % COLUMNS
            mask = 0
            for row in range(ROWS):
                if (column, row) in self.pattern:
                    mask |= 1 << row
                    self.energy[column, row] = 1.0
                else:
                    self.energy[column, row] = max(self.energy.get((column, row), 0.0), 0.28)
            self.sequencer.play(mask)
            self.step += 1
            self.next_step_frame = self.frame + round(STEP_MS / FRAME_MS)

    def _paint(self) -> None:
        """Красит только те ячейки, цвет которых изменился."""
        tone = self.colors
        lit, dim = tone["ORANGE"], tone["GROUP"]
        hot = mix(lit, "#FFFFFF", 0.6)
        idle = mix(dim, tone["TEXT"], 0.32)
        reveal = min(1.0, self.frame / INTRO_FRAMES)
        for key, item in self.pads.items():
            on = key in self.pattern
            base = (mix(dim, lit, reveal) if reveal < 1 else lit) if on else dim
            energy = self.energy.get(key, 0.0)
            if key == self.hover:
                energy = max(energy, 0.45)
            color = mix(base, hot if on else idle, min(1.0, energy)) if energy else base
            if self.painted.get(item) != color:
                self.c.itemconfigure(item, fill=color)
                self.painted[item] = color
