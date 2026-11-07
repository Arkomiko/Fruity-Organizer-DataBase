"""Вкладка «Моды»: список модов с переключателями и их кнопками."""
from __future__ import annotations

import os

import i18n
import mods as modlib
import ui as U
from i18n import tr


class ModsPage:
    """Рисует карточки модов на холсте."""

    def __init__(self, canvas, app):
        """Подключает события холста."""
        self.c, self.app, self.t = canvas, app, app.t
        self.job = None
        canvas.bind("<Configure>", lambda e: self._later())
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

    def _later(self) -> None:
        """Перерисовка после изменения размера: один раз, когда размер устоится."""
        if self.job is not None:
            self.c.after_cancel(self.job)
        self.job = self.c.after(60, self.draw)

    def draw(self) -> None:
        """Рисует вкладку заново."""
        self.job = None
        c, t = self.c, self.t
        p = t.p
        c.delete("all")
        width = c.winfo_width()
        x0, x1 = p(12), width - p(12)
        y = p(12)
        c.create_text(x0, y + p(13), text=tr("Свои моды кладите в папку mods рядом с программой. Они появятся после перезапуска."), anchor="w", fill=U.TEXT_DIM, font=t.font)
        U.Button(c, t, x1 - p(170), y, p(170), p(26), tr("Открыть папку"), self._open_folder)
        y += p(38)
        for info in self.app.mods.mods:
            y = self._card(info, x0, x1, y) + p(8)
        c.configure(scrollregion=(0, 0, width, y))

    def _card(self, info: modlib.ModInfo, x0: int, x1: int, y: int) -> int:
        """Карточка одного мода. Возвращает её нижний край."""
        c, t = self.c, self.t
        p = t.p
        enabled = info.id in self.app.s["mods_active"]
        top = y
        box = c.create_rectangle(x0, top, x1, top, fill=U.GROUP, outline=U.GROUP_LINE)
        tag = f"mod_{id(info)}"  # в имени мода могут быть скобки, а для холста это особые знаки
        led = c.create_image(x0 + p(16), y + p(16), image=t.images["led_on" if enabled else "led_off"], tags=tag)
        name = c.create_text(x0 + p(30), y + p(16), text=info.name, anchor="w", fill=U.ORANGE if enabled else U.TEXT_BRIGHT, font=t.font_bold, tags=tag)
        c.tag_bind(tag, "<Button-1>", lambda e: self.app.toggle_mod(info.id))
        details = [info.type] if info.type else []
        if info.version:
            details.append(tr("Версия {version}").format(version=info.version))
        if info.author:
            details.append(tr("Автор: {author}").format(author=info.author))
        c.create_text(x1 - p(12), y + p(16), text="   ".join(details), anchor="e", fill=U.TEXT_DIM, font=t.font)
        y += p(32)
        text = c.create_text(x0 + p(30), y, text=info.text, anchor="nw", fill=U.TEXT, font=t.font, width=x1 - x0 - p(44))
        y = c.bbox(text)[3] + p(6)
        if info.error:
            error = c.create_text(x0 + p(30), y, text=tr("Не удалось загрузить: {error}").format(error=info.error), anchor="nw", fill=U.STATUS_ERROR, font=t.font, width=x1 - x0 - p(44))
            y = c.bbox(error)[3] + p(6)
        if enabled and info.actions:
            x = x0 + p(30)
            for label, command in info.actions:
                caption = label.get(i18n.LANG) or label.get("EN-en") or ""
                button_w = t.font.measure(caption) + p(28)
                U.Button(c, t, x, y, button_w, p(26), caption, lambda cmd=command: self._run(cmd), under=U.GROUP)
                x += button_w + p(8)
            y += p(32)
        c.coords(box, x0, top, x1, y + p(4))
        c.tag_raise(led)
        c.tag_raise(name)
        return y + p(4)

    def _run(self, command) -> None:
        """Кнопка мода. Ошибка попадает в его карточку."""
        try:
            command()
        except Exception as exc:
            self.app.show_error(f"{type(exc).__name__}: {exc}")
        self.draw()

    def _open_folder(self) -> None:
        """Открывает папку своих модов, при необходимости создавая её."""
        folder = modlib.user_folder(self.app.s.folder)
        os.makedirs(folder, exist_ok=True)
        self.app._open(folder)
