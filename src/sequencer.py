"""Звук мини-секвенсора: синтез, воспроизведение и экспорт в WAV и MIDI.

Сетка: 16 шагов и 7 строк. Строки 0-3 это мелодия (верхняя самая высокая), 4 хэт, 5 снейр, 6 кик.
Рисунок это множество пар (шаг, строка). Интерфейса здесь нет, поэтому всё проверяется тестами.
"""
from __future__ import annotations

import array
import ctypes
import io
import math
import random
import struct
import threading
import time
import wave
from ctypes import wintypes
from functools import lru_cache

SAMPLE_RATE = 22050
STEPS = 16
ROWS = 7
HAT, SNARE, KICK = 4, 5, 6
MELODY_ROWS = range(HAT)
KEYS = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
# Интервалы от тоники для четырёх строк мелодии, снизу вверх.
SCALES = {
    "minor_pentatonic": ("Минорная пентатоника", (0, 3, 5, 7)),
    "major_pentatonic": ("Мажорная пентатоника", (0, 2, 4, 7)),
    "natural_minor": ("Натуральный минор", (0, 3, 7, 10)),
    "major": ("Мажор", (0, 4, 7, 11)),
}
TIMBRES = {"sine": "Синусоида", "triangle": "Треугольная", "square": "Квадратная", "bell": "Колокол"}
DRUM_NOTES = {KICK: 36, SNARE: 38, HAT: 42}  # стандартные номера General MIDI
_TWO_PI = 2 * math.pi


def melody_note(row: int, key: int, scale: str) -> int:
    """Номер ноты MIDI для строки мелодии."""
    return 60 + key + SCALES[scale][1][HAT - 1 - row]


@lru_cache(maxsize=64)
def _melody_voice(note: int, timbre: str) -> tuple[float, ...]:
    """Одна нота выбранным тембром."""
    hz = 440.0 * 2 ** ((note - 69) / 12)
    samples = []
    for i in range(int(SAMPLE_RATE * 0.5)):
        t = i / SAMPLE_RATE
        phase = _TWO_PI * hz * t
        if timbre == "triangle":
            value = 2 / math.pi * math.asin(math.sin(phase)) * math.exp(-t * 8) * 0.24
        elif timbre == "square":
            value = (1 if math.sin(phase) >= 0 else -1) * math.exp(-t * 8) * 0.12
        elif timbre == "bell":
            value = math.sin(phase + 2 * math.exp(-t * 5) * math.sin(2 * phase)) * math.exp(-t * 5) * 0.24
        else:
            value = math.sin(phase) * math.exp(-t * 6) * 0.28
        samples.append(value)
    return tuple(samples)


@lru_cache(maxsize=3)
def _drum_voice(row: int) -> tuple[float, ...]:
    """Один удар: кик, снейр или хэт."""
    noise = random.Random(row)
    samples = []
    phase = 0.0
    for i in range(int(SAMPLE_RATE * 0.25)):
        t = i / SAMPLE_RATE
        if row == KICK:
            phase += _TWO_PI * (45 + 90 * math.exp(-t * 35)) / SAMPLE_RATE
            value = math.sin(phase) * math.exp(-t * 12) * 0.7
        elif row == SNARE:
            value = (noise.uniform(-1, 1) * 0.5 * math.exp(-t * 22) + math.sin(_TWO_PI * 190 * t) * 0.25 * math.exp(-t * 18))
        else:
            value = noise.uniform(-1, 1) * math.exp(-t * 70) * 0.2
        samples.append(value)
    return tuple(samples)


class Mixer:
    """Смешивает шаги рисунка. Настройки можно менять на лету: они применяются со следующего шага."""

    def __init__(self, pattern: set, bpm: int = 90, key: int = 0, scale: str = "minor_pentatonic", timbre: str = "sine", volume: float = 0.7):
        self.pattern, self.bpm, self.key, self.scale, self.timbre, self.volume = pattern, bpm, key, scale, timbre, volume
        self.muted = False
        self.tail: list[float] = []  # хвосты нот, звучащие дольше одного шага

    def step_samples(self) -> int:
        """Длина шага в сэмплах: шаг это шестнадцатая нота."""
        return round(SAMPLE_RATE * 60 / self.bpm / 4)

    def _voices(self, step: int):
        """Звуки, которые начинаются на этом шаге."""
        for row in MELODY_ROWS:
            if (step, row) in self.pattern:
                yield _melody_voice(melody_note(row, self.key, self.scale), self.timbre)
        for row in (HAT, SNARE, KICK):
            if (step, row) in self.pattern:
                yield _drum_voice(row)

    def block(self, step: int) -> tuple[bytes, float]:
        """Звук одного шага: 16-битные сэмплы и пиковый уровень от 0 до 1."""
        count = self.step_samples()
        mix = self.tail
        for voice in self._voices(step):
            if len(mix) < len(voice):
                mix = mix + [0.0] * (len(voice) - len(mix))
            mix = [a + b for a, b in zip(mix, voice)] + mix[len(voice):]
        if len(mix) < count:
            mix = mix + [0.0] * (count - len(mix))
        self.tail = mix[count:]
        gain = 0.0 if self.muted else self.volume
        # Мягкий лимитер: много одновременных нот сжимаются плавно, а не трещат.
        limited = [math.tanh(value * gain) for value in mix[:count]]
        return array.array("h", (int(value * 32000) for value in limited)).tobytes(), max(map(abs, limited), default=0.0)


def wav_bytes(pattern: set, bpm: int, key: int, scale: str, timbre: str) -> bytes:
    """Один круг рисунка в WAV. Первый круг холостой, чтобы хвосты нот зациклились без щелчка."""
    mixer = Mixer(pattern, bpm, key, scale, timbre, 1.0)
    for step in range(STEPS):
        mixer.block(step)
    data = b"".join(mixer.block(step)[0] for step in range(STEPS))
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(data)
    return out.getvalue()


def _vlq(value: int) -> bytes:
    """Число в формате переменной длины, принятом в MIDI."""
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.insert(0, (value & 0x7F) | 0x80)
        value >>= 7
    return bytes(out)


def midi_bytes(pattern: set, bpm: int, key: int, scale: str) -> bytes:
    """Рисунок как MIDI-файл для FL Studio: мелодия на канале 1, драмы на канале 10."""
    ppq, step_ticks = 96, 24
    events = []
    for step, row in pattern:
        channel, note = (9, DRUM_NOTES[row]) if row in DRUM_NOTES else (0, melody_note(row, key, scale))
        start = step * step_ticks
        events.append((start, 1, bytes((0x90 | channel, note, 100))))
        events.append((start + step_ticks, 0, bytes((0x80 | channel, note, 0))))
    track = bytearray(b"\x00\xff\x51\x03" + (round(60_000_000 / bpm)).to_bytes(3, "big"))
    now = 0
    for tick, _order, message in sorted(events, key=lambda e: e[:2]):  # в один момент сначала отпускания
        track += _vlq(tick - now) + message
        now = tick
    track += b"\x00\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


# --------------------------------------------------------------------------------------------
# Воспроизведение через waveOut: блоки идут без пауз, и позиция известна точно
# --------------------------------------------------------------------------------------------
class _Format(ctypes.Structure):
    """Структура Windows WAVEFORMATEX."""

    _pack_ = 1
    _fields_ = [("tag", wintypes.WORD), ("channels", wintypes.WORD), ("rate", wintypes.DWORD), ("bytes_per_second", wintypes.DWORD),
                ("align", wintypes.WORD), ("bits", wintypes.WORD), ("extra", wintypes.WORD)]


class _Header(ctypes.Structure):
    """Структура Windows WAVEHDR."""

    _fields_ = [("data", ctypes.c_void_p), ("length", wintypes.DWORD), ("recorded", wintypes.DWORD), ("user", ctypes.c_size_t),
                ("flags", wintypes.DWORD), ("loops", wintypes.DWORD), ("next", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]


class _Time(ctypes.Structure):
    """Структура Windows MMTIME."""

    _fields_ = [("kind", wintypes.UINT), ("value", wintypes.DWORD), ("extra", wintypes.DWORD)]


_DONE, _TIME_SAMPLES, _QUEUED_BLOCKS = 1, 2, 3


class Player:
    """Играет рисунок по кругу в фоновом потоке. Если звукового устройства нет, шаги всё равно идут по часам."""

    def __init__(self, mixer: Mixer):
        self.mixer = mixer
        self.running = True
        self.played = 0
        self.timeline: list[tuple[int, int, float]] = []  # начало шага в сэмплах, номер шага, уровень
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def position(self) -> tuple[int, float]:
        """Шаг, звучащий сейчас, и его уровень. Вызывается из окна."""
        timeline, played = self.timeline, self.played
        for start, step, level in reversed(timeline):
            if start <= played:
                return step, level
        return 0, 0.0

    def stop(self) -> None:
        """Останавливает звук и дожидается конца потока."""
        self.running = False
        self.thread.join(timeout=1)

    def _open(self):
        """Открывает звуковое устройство. None, если его нет."""
        try:
            self.winmm = ctypes.WinDLL("winmm")
        except OSError:
            return None
        handle = wintypes.HANDLE()
        fmt = _Format(1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16, 0)
        opened = self.winmm.waveOutOpen(ctypes.byref(handle), 0xFFFFFFFF, ctypes.byref(fmt), None, None, 0)
        return handle if opened == 0 else None

    def _run(self) -> None:
        """Работа потока: держит в очереди несколько блоков и обновляет позицию."""
        handle = self._open()
        started = time.perf_counter()
        written, step = 0, 0
        slots: list[tuple[_Header, ctypes.Array]] = []
        size = ctypes.sizeof(_Header)
        while self.running:
            if handle:
                stamp = _Time(_TIME_SAMPLES, 0, 0)
                self.winmm.waveOutGetPosition(handle, ctypes.byref(stamp), ctypes.sizeof(_Time))
                self.played = stamp.value
                for slot in [s for s in slots if s[0].flags & _DONE]:
                    self.winmm.waveOutUnprepareHeader(handle, ctypes.byref(slot[0]), size)
                    slots.remove(slot)
                ready = len(slots) < _QUEUED_BLOCKS
            else:
                self.played = int((time.perf_counter() - started) * SAMPLE_RATE)
                ready = written < self.played + 2 * self.mixer.step_samples()
            if ready:
                data, level = self.mixer.block(step)
                self.timeline = [*self.timeline[-STEPS:], (written, step, level)]
                if handle:
                    buffer = ctypes.create_string_buffer(data, len(data))
                    header = _Header(ctypes.cast(buffer, ctypes.c_void_p), len(data), 0, 0, 0, 0, None, 0)
                    self.winmm.waveOutPrepareHeader(handle, ctypes.byref(header), size)
                    self.winmm.waveOutWrite(handle, ctypes.byref(header), size)
                    slots.append((header, buffer))  # буфер должен жить, пока его играет Windows
                written += len(data) // 2
                step = (step + 1) % STEPS
            else:
                time.sleep(0.005)
        if handle:
            self.winmm.waveOutReset(handle)
            for header, _buffer in slots:
                self.winmm.waveOutUnprepareHeader(handle, ctypes.byref(header), size)
            self.winmm.waveOutClose(handle)
