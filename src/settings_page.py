"""Вкладка «Настройки» и первый запуск. Каждый раздел это один метод: новый раздел добавляется новым методом."""
from __future__ import annotations

import os
import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import colorchooser, filedialog

import core
import hotkeys
import i18n
import rules
import theme as fltheme
import ui as U
from i18n import tr
from theme import mix


class Slider:
    """Горизонтальный ползунок. on_change вызывается при движении, on_commit при отпускании."""

    def __init__(self, canvas, theme, x, y, width, low, high, value, text, on_commit, on_change=None, step=1, under=None):
        """Рисует ползунок. under: цвет фона под ним."""
        self.c, self.low, self.high, self.value, self.text = canvas, low, high, value, text
        self.on_commit, self.on_change, self.step = on_commit, on_change, step
        self.x0, self.x1, self.y = x, x + width, y
        p = theme.p
        tag = self.tag = f"slider{id(self)}"
        canvas.create_rectangle(x - p(6), y - p(10), x + width + p(6), y + p(10), fill=under or U.GROUP, outline="", tags=(tag, "sec"))
        canvas.create_rectangle(x, y - p(2), x + width, y + p(2), fill=U.BOX, outline=U.BOX_LINE, tags=(tag, "sec"))
        self.fill = canvas.create_rectangle(x, y - p(1), x, y + p(2), fill=U.ORANGE, outline="", tags=(tag, "sec"))
        self.half = p(4)
        self.thumb = canvas.create_rectangle(x, y - p(8), x, y + p(8), fill=U.BTN_TOP, outline=U.BTN_BORDER, tags=(tag, "sec"))
        self.label = canvas.create_text(x + width + p(14), y, text="", anchor="w", fill=U.TEXT_SOFT, font=theme.font, tags="sec")
        canvas.tag_bind(tag, "<Button-1>", self._drag)
        canvas.tag_bind(tag, "<B1-Motion>", self._drag)
        canvas.tag_bind(tag, "<ButtonRelease-1>", lambda e: self.on_commit(self.value))
        self._paint()

    def _paint(self) -> None:
        """Ставит заливку, ручку и подпись по значению."""
        x = self.x0 + (self.value - self.low) / (self.high - self.low) * (self.x1 - self.x0)
        self.c.coords(self.fill, self.x0 + 1, self.y - 1, x, self.y + 2)
        self.c.coords(self.thumb, x - self.half, self.y - self.half * 2, x + self.half, self.y + self.half * 2)
        self.c.itemconfigure(self.label, text=self.text.format(value=self.value))

    def _drag(self, event) -> None:
        """Переводит положение мыши в значение."""
        share = max(0.0, min(1.0, (event.x - self.x0) / (self.x1 - self.x0)))
        value = self.low + round(share * (self.high - self.low) / self.step) * self.step
        if value != self.value:
            self.value = value
            self._paint()
            if self.on_change:
                self.on_change(value)


class Table:
    """Небольшая прокручиваемая таблица, нарисованная на холсте страницы."""

    def __init__(self, canvas, theme, box, columns, rows, on_open=None, empty=""):
        """box: границы таблицы; columns: (заголовок, доля ширины); rows: строки."""
        self.c, self.t, self.box, self.columns = canvas, theme, box, columns
        self.rows, self.on_open, self.empty = rows, on_open, empty
        self.top = 0
        self.selected = 0 if rows else None
        self.row_h = max(theme.p(19), theme.font.metrics("linespace") + theme.p(2))
        self.tag = f"table{id(self)}"
        self.draw()

    @property
    def capacity(self) -> int:
        """Сколько строк помещается."""
        return max(1, (self.box[3] - self.box[1] - self.row_h) // self.row_h)

    def draw(self) -> None:
        """Рисует заголовок и видимые строки."""
        c, t = self.c, self.t
        p = t.p
        x0, y0, x1, y1 = self.box
        c.delete(self.tag)
        tags = (self.tag, "sec")
        c.create_rectangle(x0, y0, x1, y1, fill=U.ROW_A, outline=U.GRID_LINE, tags=tags)
        c.create_rectangle(x0 + 1, y0 + 1, x1, y0 + self.row_h, fill=U.HEADER, outline="", tags=tags)
        widths = [round((x1 - x0) * share) for _, share in self.columns]
        x = x0 + p(6)
        for (title, _), width in zip(self.columns, widths):
            c.create_text(x, y0 + self.row_h // 2, text=t.fit(title, width - p(8)), anchor="w", fill=U.TEXT_DIM, font=t.font, tags=tags)
            x += width
        for r, row in enumerate(self.rows[self.top:self.top + self.capacity]):
            index = self.top + r
            y = y0 + self.row_h * (r + 1)
            selected = index == self.selected
            fill = U.SELECT if selected else (U.ROW_B if index % 2 else U.ROW_A)
            c.create_rectangle(x0 + 1, y, x1, y + self.row_h, fill=fill, outline="", tags=tags)
            x = x0 + p(6)
            for value, width in zip(row, widths):
                c.create_text(x, y + self.row_h // 2, text=t.fit(str(value), width - p(8)), anchor="w", fill=U.WHITE if selected else U.TEXT, font=t.font, tags=tags)
                x += width
        if not self.rows and self.empty:
            c.create_text(x0 + p(8), y0 + self.row_h + p(14), text=self.empty, anchor="w", fill=U.TEXT_DIM, font=t.font, tags=tags)

    def _index_at(self, y: int):
        """Номер строки по координате y (или None)."""
        index = self.top + (y - self.box[1] - self.row_h) // self.row_h
        return index if y > self.box[1] + self.row_h and 0 <= index < len(self.rows) else None

    def _inside(self, event) -> bool:
        """Попала ли мышь в таблицу."""
        x0, y0, x1, y1 = self.box
        return x0 <= event.x <= x1 and y0 <= event.y <= y1

    def click(self, event) -> None:
        """Выделяет строку."""
        index = self._index_at(event.y) if self._inside(event) else None
        if index is not None:
            self.selected = index
            self.draw()

    def double(self, event) -> None:
        """Двойной клик открывает строку."""
        if self._inside(event) and self._index_at(event.y) is not None and self.on_open:
            self.on_open()

    def wheel(self, event) -> bool:
        """Прокрутка колесом. True, если мышь над таблицей."""
        if not self._inside(event):
            return False
        top = max(0, min(max(0, len(self.rows) - self.capacity), self.top + (-3 if event.delta > 0 else 3)))
        if top != self.top:
            self.top = top
            self.draw()
        return True


class SettingsPage:
    """Вкладка настроек: меню разделов слева, содержимое справа."""
    SECTIONS = (("general", "Общие"), ("layout", "Раскладка"), ("vendors", "Производители"), ("rules", "Правила"),
                ("backups", "Бэкапы"), ("look", "Оформление"), ("keys", "Клавиши"), ("data", "Данные"))

    def __init__(self, canvas, app):
        """Подключает события холста."""
        self.c, self.app, self.t = canvas, app, app.t
        self.section = app.settings_section
        self.format_drag = None
        self.tables: list[Table] = []
        self.build_job = None
        canvas.bind("<Configure>", self._configure)
        # На холст, а не на элементы: обработчики перерисовывают элементы под самой мышью.
        canvas.bind("<MouseWheel>", lambda e: any(table.wheel(e) for table in self.tables))
        canvas.bind("<Button-1>", lambda e: [table.click(e) for table in self.tables])
        canvas.bind("<Double-Button-1>", lambda e: [table.double(e) for table in self.tables])
        canvas.bind("<B1-Motion>", self._format_motion)
        canvas.bind("<ButtonRelease-1>", lambda e: self._format_release())

    def _configure(self, _event) -> None:
        """Размер изменился: перестраиваем страницу, когда он перестанет меняться."""
        if self.build_job is not None:
            self.c.after_cancel(self.build_job)
        if hasattr(self, "status"):
            self.build_job = self.c.after(60, self.build)
        else:
            self.build()

    def build(self) -> None:
        """Рисует меню разделов и текущий раздел."""
        self.build_job = None
        c, t = self.c, self.t
        p = t.p
        c.delete("all")
        width, height = c.winfo_width(), c.winfo_height()
        self.nav_w = p(150)
        c.create_rectangle(p(6), p(10), self.nav_w, height - p(8), fill=U.GROUP, outline="")
        c.create_line(p(6), height - p(8), self.nav_w, height - p(8), fill=U.GROUP_LINE)
        self.nav_items = {}
        row_h = p(30)
        for i, (name, label) in enumerate(self.SECTIONS):
            y = p(14) + i * row_h
            tag = f"nav_{name}"
            bar = c.create_rectangle(p(6), y, p(9), y + row_h - p(2), fill=U.GROUP, outline="", tags=tag)
            face = c.create_rectangle(p(9), y, self.nav_w, y + row_h - p(2), fill=U.GROUP, outline="", tags=tag)
            text = c.create_text(p(18), y + row_h // 2 - p(1), text=t.fit(tr(label), self.nav_w - p(26)), anchor="w", fill=U.TEXT, font=t.font, tags=tag)
            self.nav_items[name] = (bar, face, text)
            c.tag_bind(tag, "<Button-1>", lambda e, n=name: self.open(n))
            c.tag_bind(tag, "<Enter>", lambda e, n=name: self._nav_paint(n, hover=True))
            c.tag_bind(tag, "<Leave>", lambda e, n=name: self._nav_paint(n))
        self.x0, self.x1 = self.nav_w + p(8), width - p(6)
        self.status = c.create_text(self.x0 + p(2), height - p(14), text=self.app.hint_text, anchor="w", fill=U.TEXT_SOFT, font=t.font_bold)
        self.height = height - p(26)
        self.draw_section()

    def _nav_paint(self, name: str, hover: bool = False) -> None:
        """Красит пункт меню по состоянию."""
        bar, face, text = self.nav_items[name]
        on = name == self.section
        self.c.itemconfigure(bar, fill=U.ORANGE if on else U.GROUP)
        self.c.itemconfigure(face, fill=U.TAB_ON if on else mix(U.GROUP, U.TEXT, 0.08) if hover else U.GROUP)
        self.c.itemconfigure(text, fill=U.ORANGE if on else U.TEXT)

    def open(self, name: str) -> None:
        """Переключает раздел с плавным переходом."""
        if name != self.section:
            self.section = self.app.settings_section = name
            x, y = self.c.winfo_rootx() + self.x0, self.c.winfo_rooty()
            self.app.fade_rect(x, y, self.c.winfo_width() - self.x0, self.c.winfo_height())
            self.draw_section()

    def draw_section(self) -> None:
        """Рисует содержимое текущего раздела: метод _<имя раздела>."""
        self.c.delete("sec")
        self.tables = []
        self.app.undo_btn = None
        for name in self.nav_items:
            self._nav_paint(name)
        self.format_drag = None
        self.app.paint = self.c
        getattr(self, "_" + self.section)()
        self.app.paint = self.app.left
        self.app._update_undo_button()

    def set_status(self, text: str) -> None:
        """Текст в строке подсказок."""
        self.c.itemconfigure(self.status, text=text)

    # ------------------------------------------------------------------ строительные блоки
    def group(self, y: int, h: int, title: str, x0=None, x1=None) -> None:
        """Рамка группы настроек."""
        self.app._group(y, h, title, "sec", x0=self.x0 if x0 is None else x0, x1=self.x1 if x1 is None else x1)

    def label(self, x, y, text, tone=None) -> None:
        """Подпись."""
        self.c.create_text(x, y, text=text, anchor="w", fill=tone or U.TEXT_SOFT, font=self.t.font, tags="sec")

    def button(self, x, y, w, text, command, h=None):
        """Кнопка."""
        return U.Button(self.c, self.t, x, y, w, h or self.t.p(26), text, command, tags=("sec",), under=U.GROUP)

    def dropdown(self, x, y, w, current, options, pick) -> None:
        """Кнопка с меню из пар (значение, подпись)."""
        def popup():
            """Открывает меню под кнопкой."""
            menu = self.app._menu()
            for value, label in options:
                menu.add_command(label=label, command=lambda v=value: pick(v))
            menu.popup(self.c.winfo_rootx() + x, self.c.winfo_rooty() + y + self.t.p(26), w)
        label = next((text for value, text in options if value == current), str(current))
        self.button(x, y, w, self.t.fit(label, w - self.t.p(30)), popup)
        self.c.create_image(x + w - self.t.p(12), y + self.t.p(13), image=self.t.images["caret"], state="disabled", tags="sec")

    def led(self, x, y, text, key, hint="", command=None) -> None:
        """Индикатор-переключатель настройки."""
        self.app._led(x, y, text, key, "sec", hint, command)

    def choice_row(self, y, text, key, options, command=None) -> None:
        """Подпись и выпадающий список, связанные с одной настройкой."""
        p = self.t.p
        self.label(self.x0 + p(14), y + p(13), text)
        def pick(value):
            """Сохраняет выбор."""
            self.app.s[key] = value
            self.app.s.save()
            if command:
                command()
            self.draw_section()
        self.dropdown(self.x0 + p(250), y, p(320), self.app.s[key], options, pick)

    # ------------------------------------------------------------------ разделы
    def _general(self) -> None:
        """Раздел «Общие»."""
        app, p = self.app, self.t.p
        y = p(10)
        self.group(y, p(190), tr("Запуск и окно"))
        y0 = y + p(30)
        self.label(self.x0 + p(14), y0 + p(13), tr("Язык"))
        self.dropdown(self.x0 + p(250), y0, p(320), i18n.LANG, list(i18n.available().items()), app.set_language)
        self.choice_row(y0 + p(32), tr("При запуске"), "startup_action",
                        [("open", tr("Просто открыть")), ("new", tr("Показать неорганизованные")), ("propose", tr("Предложить разложить"))])
        self.choice_row(y0 + p(64), tr("Кнопка закрытия"), "close_action", [("exit", tr("Закрывает программу")), ("tray", tr("Сворачивает в трей"))])
        self.choice_row(y0 + p(96), tr("Двойной клик по плагину"), "double_click",
                        [("plugin", tr("Открывает вкладку «Плагин»")), ("folder", tr("Открывает папку плагина")), ("star", tr("Ставит или снимает звезду")), ("none", tr("Ничего не делает"))])
        self.led(self.x0 + p(14), y0 + p(142), tr("Поверх всех окон"), "always_on_top", "", app._apply_topmost)
        y += p(198)
        self.group(y, p(66), tr("База плагинов FL Studio"))
        U.IconButton(self.c, self.t, self.x0 + p(29), y + p(43), "folder", self._choose_database, U.GROUP, ("sec",))
        self.label(self.x0 + p(56), y + p(43), self.t.fit(app.db or tr("Папка не найдена: выберите её"), self.x1 - self.x0 - p(70), middle=True), U.TEXT if app.db else U.ORANGE)

    def _choose_database(self) -> None:
        """Выбор папки базы."""
        self.app.choose_database()
        self.draw_section()

    def _layout(self) -> None:
        """Раздел «Раскладка»."""
        app, p = self.app, self.t.p
        y = p(10)
        self.group(y, p(184), tr("Раскладка папок"))
        y0 = y + p(30)
        for offset, kind, text in ((0, "Effects", tr("Эффекты")), (p(32), "Generators", tr("Генераторы"))):
            self.label(self.x0 + p(14), y0 + offset + p(13), text)
            self._layout_button(y0 + offset, kind)
        languages = [("", tr("Как язык интерфейса")), *i18n.available().items()]
        self.choice_row(y0 + p(64), tr("Язык папок назначения"), "folder_language", languages, app._update_plugin_page)
        self.led(self.x0 + p(14), y0 + p(112), tr("Убирать LLC, GmbH, Inc. из названий папок"), "strip_suffix", "", app._update_plugin_page)
        self.led(self.x0 + p(14), y0 + p(138), tr("Переносить из папки New"), "move_from_new",
                 tr("После раскладки плагин исчезает из списка New в FL Studio. Кнопка «Отменить» вернёт его обратно."))
        y += p(192)
        rows = len(app.s["format_order"])
        self.group(y, p(36) + rows * p(24), tr("Порядок форматов для одной копии"))
        self.label(self.x0 + p(250), y + p(10), tr("Перетащите строку выше или ниже"), U.TEXT_DIM)
        self.format_box = (self.x0 + p(12), y + p(30), self.x0 + p(240), y + p(30) + rows * p(24))
        self._draw_formats()

    def _layout_button(self, y, kind) -> None:
        """Список раскладок для эффектов или генераторов."""
        app, p = self.app, self.t.p
        key = "layout" if kind == "Effects" else "layout_generators"
        options = [(rules.LAYOUTS[k], tr(rules.LAYOUT_LABELS[k])) for k in rules.LAYOUTS]
        options.append(("?", tr("Свой шаблон…")))

        def pick(value):
            """Применяет раскладку или открывает свой шаблон."""
            if value == "?":
                app.custom_layout(key)
            else:
                app.set_layout(value, key)
            self.draw_section()
        self.dropdown(self.x0 + p(250), y, p(320), app.s[key], options, pick)

    def _draw_formats(self) -> None:
        """Рисует список форматов, который можно перетаскивать."""
        c, t, p = self.c, self.t, self.t.p
        c.delete("fmt")
        x0, y0, x1, _ = self.format_box
        order = self.app.s["format_order"]
        for i, name in enumerate(order):
            y = y0 + i * p(24)
            tag = (f"fmt_{name}", "fmt", "sec")
            held = self.format_drag == name
            c.create_rectangle(x0, y, x1, y + p(22), fill=U.SELECT if held else U.BOX, outline=U.BOX_LINE, tags=tag)
            c.create_text(x0 + p(10), y + p(11), text=str(i + 1), anchor="w", fill=U.TEXT_DIM, font=t.font, tags=tag)
            c.create_text(x0 + p(30), y + p(11), text=name, anchor="w", fill=U.WHITE if held else U.TEXT, font=t.font, tags=tag)
            for dot in range(3):
                c.create_rectangle(x1 - p(16), y + p(7) + dot * p(3), x1 - p(8), y + p(8) + dot * p(3), fill=U.TEXT_DIM, outline="", tags=tag)
            c.tag_bind(tag[0], "<Button-1>", lambda e, n=name: self._format_press(n))

    def _format_press(self, name: str) -> None:
        """Начало перетаскивания формата."""
        self.format_drag = name
        self._draw_formats()

    def _format_motion(self, event) -> None:
        """Двигает формат вслед за мышью."""
        order = self.app.s["format_order"]
        if self.format_drag not in order:
            return
        index = max(0, min(len(order) - 1, (event.y - self.format_box[1]) // self.t.p(24)))
        if order[index] != self.format_drag:
            order.remove(self.format_drag)
            order.insert(index, self.format_drag)
            self._draw_formats()

    def _format_release(self) -> None:
        """Конец перетаскивания: порядок сохраняется."""
        if self.format_drag is None:
            return
        self.format_drag = None
        self.app.s.save()
        self._draw_formats()

    def _table_buttons(self, y, buttons) -> None:
        """Ряд кнопок под таблицей."""
        p = self.t.p
        x = self.x0 + p(12)
        for text, command in buttons:
            self.button(x, y, p(110), text, command)
            x += p(118)

    def _vendors(self) -> None:
        """Раздел «Производители»."""
        p = self.t.p
        bottom = self.height
        self.group(p(10), bottom - p(10), tr("Объединение производителей"))
        aliases = self.app.s["vendor_aliases"]
        self.alias_rows = sorted(aliases.items(), key=lambda kv: kv[0].casefold())
        self.label(self.x0 + p(14), p(42), tr("Заменяет название производителя в списке и в папках. Например, Direct на MiniMeters."), U.TEXT_DIM)
        box = (self.x0 + p(12), p(56), self.x1 - p(12), bottom - p(42))
        self.alias_table = Table(self.c, self.t, box, ((tr("Как в плагине"), 0.5), (tr("Как показывать"), 0.5)), self.alias_rows, self._edit_alias, tr("Пока пусто."))
        self.tables.append(self.alias_table)
        self._table_buttons(bottom - p(34), ((tr("Добавить"), self._add_alias), (tr("Изменить"), self._edit_alias), (tr("Удалить"), self._remove_alias)))

    def _alias_dialog(self, source: str, target: str) -> None:
        """Окно добавления или правки замены."""
        vendors = sorted({p.raw_vendor for p in self.app.plugins if p.raw_vendor}, key=str.casefold)
        dialog = U.Dialog(self.app.root, self.t, tr("Объединение производителей"), "", [tr("Применить"), tr("Отмена")], width=520,
                          fields=[(tr("Как в плагине"), source, None, vendors), (tr("Как показывать"), target, None, None)])
        if dialog.result != 0:
            return
        new_source, new_target = (value.strip() for value in dialog.values)
        if new_source and new_target:
            aliases = self.app.s["vendor_aliases"]
            aliases.pop(source, None)
            aliases[new_source] = new_target
            self.app.settings_changed()
            self.draw_section()

    def _add_alias(self) -> None:
        """Новая замена."""
        self._alias_dialog("", "")

    def _edit_alias(self) -> None:
        """Правка выбранной замены."""
        table = self.alias_table
        if table.selected is not None and table.rows:
            self._alias_dialog(*table.rows[table.selected])

    def _remove_alias(self) -> None:
        """Удаление выбранной замены."""
        table = self.alias_table
        if table.selected is not None and table.rows:
            self.app.s["vendor_aliases"].pop(table.rows[table.selected][0], None)
            self.app.settings_changed()
            self.draw_section()

    def _rules(self) -> None:
        """Раздел «Правила»."""
        p = self.t.p
        bottom = self.height
        self.group(p(10), bottom - p(10), tr("Ваши правила назначения"))
        self.label(self.x0 + p(14), p(42), tr("Первое подошедшее правило важнее автоматики. В условиях работают регулярные выражения."), U.TEXT_DIM)
        kinds = {"": tr("Любой"), "Effects": tr("Эффекты"), "Generators": tr("Генераторы")}
        rows = [(rules.purpose_label(r.get("purpose", "")), r.get("name", ""), r.get("vendor", ""), kinds.get(r.get("kind", ""), "")) for r in self.app.s["purpose_rules"]]
        box = (self.x0 + p(12), p(56), self.x1 - p(12), bottom - p(42))
        columns = ((tr("Назначение"), 0.28), (tr("Название"), 0.3), (tr("Вендор"), 0.26), (tr("Тип"), 0.16))
        self.rule_table = Table(self.c, self.t, box, columns, rows, self._edit_rule, tr("Пока пусто."))
        self.rule_table.selected = min(getattr(self, "rule_selected", 0), len(rows) - 1) if rows else None
        self.rule_table.draw()
        self.tables.append(self.rule_table)
        self._table_buttons(bottom - p(34), ((tr("Добавить"), self._add_rule), (tr("Изменить"), self._edit_rule), (tr("Удалить"), self._remove_rule),
                                             (tr("Выше"), lambda: self._move_rule(-1)), (tr("Ниже"), lambda: self._move_rule(1))))

    def _rule_dialog(self, rule: dict) -> dict | None:
        """Окно правила. Возвращает правило или None, если отменено или неверно."""
        purposes = sorted(((k, rules.purpose_label(k)) for k in rules.PURPOSES), key=lambda kv: kv[1].casefold())
        kinds = [("", tr("Любой")), ("Effects", tr("Эффекты")), ("Generators", tr("Генераторы"))]
        dialog = U.Dialog(self.app.root, self.t, tr("Ваши правила назначения"), "", [tr("Применить"), tr("Отмена")], width=520,
                          fields=[(tr("Назначение"), rule.get("purpose", "reverb"), purposes, None), (tr("Название"), rule.get("name", ""), None, None),
                                  (tr("Вендор"), rule.get("vendor", ""), None, None), (tr("Тип"), rule.get("kind", ""), kinds, None)])
        if dialog.result != 0:
            return None
        purpose, name, vendor, kind = dialog.values
        try:
            re.compile(name)
            re.compile(vendor)
        except re.error as exc:
            U.Dialog(self.app.root, self.t, tr("Ошибка"), tr("Ошибка в шаблоне: {error}").format(error=exc), [tr("Понятно")])
            return None
        if not (name or vendor or kind):
            U.Dialog(self.app.root, self.t, tr("Ошибка"), tr("Заполните хотя бы одно условие."), [tr("Понятно")])
            return None
        return {"purpose": purpose, "name": name, "vendor": vendor, "kind": kind}

    def _add_rule(self) -> None:
        """Новое правило."""
        rule = self._rule_dialog({})
        if rule:
            self.app.s["purpose_rules"].append(rule)
            self.rule_selected = len(self.app.s["purpose_rules"]) - 1
            self.app.settings_changed()
            self.draw_section()

    def _edit_rule(self) -> None:
        """Правка выбранного правила."""
        index = self.rule_table.selected
        if index is None:
            return
        rule = self._rule_dialog(self.app.s["purpose_rules"][index])
        if rule:
            self.app.s["purpose_rules"][index] = rule
            self.rule_selected = index
            self.app.settings_changed()
            self.draw_section()

    def _remove_rule(self) -> None:
        """Удаление выбранного правила."""
        index = self.rule_table.selected
        if index is not None:
            del self.app.s["purpose_rules"][index]
            self.rule_selected = index
            self.app.settings_changed()
            self.draw_section()

    def _move_rule(self, delta: int) -> None:
        """Двигает правило: порядок важен, побеждает первое."""
        index = self.rule_table.selected
        items = self.app.s["purpose_rules"]
        if index is not None and 0 <= index + delta < len(items):
            items[index], items[index + delta] = items[index + delta], items[index]
            self.rule_selected = index + delta
            self.app.settings_changed()
            self.draw_section()

    def _backups(self) -> None:
        """Раздел «Бэкапы»."""
        app, s, p = self.app, self.app.s, self.t.p
        y = p(10)
        self.group(y, p(164), tr("Резервные копии"))
        self.led(self.x0 + p(14), y + p(42), tr("Бэкап перед каждым изменением"), "auto_backup",
                 tr("Перед любым изменением базы сохранять её в ZIP-архив в папке Backups рядом с программой."))
        self.label(self.x0 + p(14), y + p(72), tr("Хранить бэкапов"))
        def keep(value):
            """Сохраняет число хранимых бэкапов."""
            s["backup_keep"] = value
            s.save()
        Slider(self.c, self.t, self.x0 + p(250), y + p(72), p(260), 5, 100, s["backup_keep"], "{value}", keep, step=5)
        bw = p(130)
        self.button(self.x0 + p(12), y + p(94), bw, tr("Бэкап"), app.backup_click)
        self.button(self.x0 + p(12) + bw + p(8), y + p(94), bw, tr("Восстановить"), app.restore_click)
        app.undo_btn = self.button(self.x0 + p(12) + 2 * (bw + p(8)), y + p(94), bw, tr("Отменить"), app.undo_click)
        self.button(self.x0 + p(12) + 3 * (bw + p(8)), y + p(94), bw, tr("Открыть папку"), lambda: self._open_backups())
        count = len(core.list_backups(s.backups))
        self.label(self.x0 + p(14), y + p(140), self.t.fit(f"{s.backups}  ({count})", self.x1 - self.x0 - p(28), middle=True), U.TEXT_DIM)
        y += p(172)
        self.group(y, p(128), tr("Спрашивать подтверждение"))
        for i, (key, text) in enumerate((("preview", tr("Копирование")), ("confirm_move", tr("Перемещение")), ("confirm_delete", tr("Удаление")), ("confirm_restore", tr("Восстановление")))):
            self.led(self.x0 + p(14), y + p(38) + i * p(22), text, key, "", app._build_left if key == "preview" else None)

    def _open_backups(self) -> None:
        """Открывает папку бэкапов."""
        os.makedirs(self.app.s.backups, exist_ok=True)
        self.app._open(self.app.s.backups)

    def _look(self) -> None:
        """Раздел «Оформление»."""
        app, s, p = self.app, self.app.s, self.t.p
        y = p(10)
        custom = s["theme_mode"] == "custom"
        self.group(y, p(84) if custom else p(66), tr("Цветовая тема"))
        y0 = y + p(30)
        self.label(self.x0 + p(14), y0 + p(13), tr("Тема"))
        def pick(value):
            """Меняет тему и перестраивает окно."""
            s["theme_mode"] = value
            s.save()
            app.rebuild_ui()
        self.dropdown(self.x0 + p(250), y0, p(320), s["theme_mode"], [("classic", tr("Классика")), ("fl", tr("Как в моей FL")), ("custom", tr("Свои"))], pick)
        if s["theme_mode"] == "fl":
            name = os.path.basename(app.theme_path)[:-9] if app.theme_path else "—"
            self.label(self.x0 + p(584), y0 + p(13), self.t.fit(name, self.x1 - self.x0 - p(596)), U.TEXT_DIM)
        if custom:
            self._swatches(y0 + p(30))
        y += p(92) if custom else p(74)
        self.group(y, p(166), tr("Масштаб и шрифт"))
        y0 = y + p(42)
        self.label(self.x0 + p(14), y0, tr("Масштаб интерфейса"))
        Slider(self.c, self.t, self.x0 + p(250), y0, p(260), 75, 200, s["ui_scale"], "{value} %", app.set_scale)
        self.label(self.x0 + p(14), y0 + p(36), tr("Шрифт"))
        self.button(self.x0 + p(250), y0 + p(23), p(260), self.t.fit(s["font_family"], p(240)), self._pick_font)
        self.button(self.x0 + p(518), y0 + p(23), p(110), tr("Сбросить"), self._reset_font)
        self.label(self.x0 + p(14), y0 + p(68), tr("Размер шрифта"))
        def size(value):
            """Меняет размер шрифта и перестраивает окно."""
            if value != s["font_size"]:
                s["font_size"] = value
                s.save()
                app.rebuild_ui()
        Slider(self.c, self.t, self.x0 + p(250), y0 + p(68), p(260), 9, 15, s["font_size"], "{value} px", size)
        self.led(self.x0 + p(14), y0 + p(102), tr("Мягкие переходы и анимация"), "animations", "", app.apply_motion)
        y += p(174)
        columns = [(key, label) for key, label, _ in U.columns() if key not in ("fav", "name")]
        self.group(y, p(34) + (len(columns) + 2) // 3 * p(22), tr("Колонки списка"))
        column_w = (self.x1 - self.x0 - p(24)) // 3
        for i, (key, label) in enumerate(columns):
            x = self.x0 + p(14) + i % 3 * column_w
            self._column_led(x, y + p(36) + i // 3 * p(22), key, label)
        y += p(42) + (len(columns) + 2) // 3 * p(22)
        self.group(y, p(128), tr("Статус"))
        y0 = y + p(30)
        self.label(self.x0 + p(14), y0 + p(13), tr("Вид статуса"))

        def style(value):
            s["status_style"] = value
            s.save()
            app.rebuild_ui()
        self.dropdown(self.x0 + p(250), y0, p(320), s["status_style"], [("text", tr("Текст")), ("icons", tr("Значки"))], style)
        self._status_color(y0 + p(32), tr("Цвет: работает"), "status_ok", U.STANDARD_STATUS_OK)
        self._status_color(y0 + p(64), tr("Цвет: ошибка"), "status_error", U.STANDARD_STATUS_ERROR)

    def _status_color(self, y, text, key, standard) -> None:
        """Строка цвета статуса: палитра открывается, только если выбран свой цвет."""
        c, t, s, p = self.c, self.t, self.app.s, self.t.p
        self.label(self.x0 + p(14), y + p(13), text)
        current = s[key]

        def mode(value):
            s[key] = (current or standard) if value == "custom" else ""
            s.save()
            self.app.rebuild_ui()
        self.dropdown(self.x0 + p(250), y, p(320), "custom" if current else "standard", [("standard", tr("Стандартный")), ("custom", tr("Свой"))], mode)
        tag = f"swatch_{key}"
        x = self.x0 + p(580)
        c.create_rectangle(x, y + p(3), x + p(34), y + p(23), fill=current or standard, outline=U.BOX_LINE, stipple="" if current else "gray50", tags=("sec", tag))
        if current:
            c.tag_bind(tag, "<Button-1>", lambda e: self._pick_status_color(key, current))

    def _pick_status_color(self, key: str, color: str) -> None:
        """Окно выбора цвета статуса."""
        _rgb, picked = colorchooser.askcolor(color=color, parent=self.app.root)
        if picked:
            self.app.s[key] = picked.upper()
            self.app.s.save()
            self.app.rebuild_ui()

    def _column_led(self, x, y, key, label) -> None:
        """Переключатель видимости колонки."""
        c, t, s = self.c, self.t, self.app.s
        tag = f"col_{key}"
        on = key not in s["hidden_columns"]
        image = c.create_image(x, y, anchor="w", image=t.images["led_on" if on else "led_off"], tags=("sec", tag))
        c.create_text(x + t.p(18), y, text=label, anchor="w", fill=U.TEXT_SOFT, font=t.font, tags=("sec", tag))
        def toggle(_event):
            """Показывает или скрывает колонку."""
            visible = key in s["hidden_columns"]
            self.app.set_column_visible(key, visible)
            c.itemconfigure(image, image=t.images["led_on" if visible else "led_off"])
        c.tag_bind(tag, "<Button-1>", toggle)

    def _swatches(self, y) -> None:
        """Образцы цветов для своей темы."""
        c, t, s, p = self.c, self.t, self.app.s, self.t.p
        names = {"PANEL": tr("Фон"), "TEXT": tr("Текст"), "ORANGE": tr("Акцент"), "SELECT": tr("Выделение"), "LED": tr("Индикатор")}
        x = self.x0 + p(14)
        for key, stock in fltheme.CUSTOM_KEYS.items():
            color = s["custom_colors"].get(key) or stock
            tag = f"swatch_{key}"
            c.create_rectangle(x, y + p(3), x + p(22), y + p(19), fill=color, outline=U.BOX_LINE, tags=("sec", tag))
            c.create_text(x + p(28), y + p(11), text=names[key], anchor="w", fill=U.TEXT_SOFT, font=t.font, tags=("sec", tag))
            c.tag_bind(tag, "<Button-1>", lambda e, k=key, v=color: self._pick_color(k, v))
            x += p(40) + t.font.measure(names[key]) + p(10)
        self.button(x + p(4), y, p(110), tr("Сбросить"), self._reset_colors, h=p(22))

    def _pick_color(self, key: str, color: str) -> None:
        """Окно выбора цвета."""
        _rgb, picked = colorchooser.askcolor(color=color, parent=self.app.root)
        if picked:
            self.app.s["custom_colors"][key] = picked.upper()
            self.app.s.save()
            self.app.rebuild_ui()

    def _reset_colors(self) -> None:
        """Возврат к стандартным цветам."""
        self.app.s["custom_colors"] = {}
        self.app.s.save()
        self.app.rebuild_ui()

    def _pick_font(self) -> None:
        """Окно выбора шрифта."""
        names = sorted({n for n in tkfont.families(self.app.root) if not n.startswith("@")}, key=str.casefold)
        dialog = U.Dialog(self.app.root, self.t, tr("Шрифт"), "", [tr("Применить"), tr("Отмена")], width=420, choices=names, current=self.app.s["font_family"])
        if dialog.result == 0 and dialog.choice:
            self.app.s["font_family"] = dialog.choice
            self.app.s.save()
            self.app.rebuild_ui()

    def _reset_font(self) -> None:
        """Возврат к стандартному шрифту и размеру."""
        s = self.app.s
        s["font_family"], s["font_size"] = s.DEFAULTS["font_family"], s.DEFAULTS["font_size"]
        s.save()
        self.app.rebuild_ui()

    def _keys(self) -> None:
        """Раздел «Клавиши»."""
        p = self.t.p
        bottom = self.height
        self.group(p(10), bottom - p(10), tr("Горячие клавиши"))
        self.label(self.x0 + p(14), p(42), tr("Дважды щёлкните строку, чтобы назначить другое сочетание."), U.TEXT_DIM)
        saved = self.app.s["hotkeys"]
        rows = [(tr(label), hotkeys.display(saved.get(action, default)) if saved.get(action, default) else "—") for action, label, default in hotkeys.ACTIONS]
        box = (self.x0 + p(12), p(56), self.x1 - p(12), bottom - p(42))
        self.key_table = Table(self.c, self.t, box, ((tr("Действие"), 0.6), (tr("Клавиши"), 0.4)), rows, self._capture_key)
        self.tables.append(self.key_table)
        self._table_buttons(bottom - p(34), ((tr("Изменить"), self._capture_key), (tr("Сбросить"), self._reset_keys)))
        self.label(self.x0 + p(250), bottom - p(21), self.t.fit(tr("Сочетания работают на любой раскладке: важна сама клавиша, а не её буква."), self.x1 - self.x0 - p(262)), U.TEXT_DIM)

    def _capture_key(self) -> None:
        """Ждёт новое сочетание для выбранного действия."""
        index = self.key_table.selected
        if index is None:
            return
        action = hotkeys.ACTIONS[index][0]

        def on_key(event, dialog):
            """Обрабатывает нажатие в окне ожидания."""
            if event.keycode == 27:
                dialog._close(1)
            elif event.keycode == 46 and not event.state & (hotkeys.CTRL | hotkeys.ALT | hotkeys.SHIFT):
                dialog.text = ""
                dialog._close(0)
            else:
                text = hotkeys.shortcut(event.keycode, event.state)
                if text:
                    dialog.text = text
                    dialog._close(0)

        dialog = U.Dialog(self.app.root, self.t, tr(hotkeys.ACTIONS[index][1]), tr("Нажмите сочетание клавиш. Esc отменяет, Delete убирает сочетание."), [tr("Отмена")], width=420, on_key=on_key)
        if dialog.result == 0:
            self.app.s["hotkeys"] = hotkeys.assign(self.app.s["hotkeys"], action, dialog.text)
            self.app.s.save()
            self.app.bind_hotkeys()
            self.draw_section()

    def _reset_keys(self) -> None:
        """Возврат к сочетаниям по умолчанию."""
        self.app.s["hotkeys"] = {}
        self.app.s.save()
        self.app.bind_hotkeys()
        self.draw_section()

    def _data(self) -> None:
        """Раздел «Данные»."""
        app, s, p = self.app, self.app.s, self.t.p
        bw = p(170)
        y = p(10)
        self.group(y, p(84), tr("Журнал действий"))
        self.label(self.x0 + p(14), y + p(38), tr("Что, куда и когда скопировано. Старые записи перезаписываются после 20 МБ."), U.TEXT_DIM)
        self.button(self.x0 + p(12), y + p(50), bw, tr("Открыть журнал"), self._show_log)
        size = os.path.getsize(s.log.path) / 1048576 if os.path.exists(s.log.path) else 0
        self.label(self.x0 + p(12) + bw + p(12), y + p(63), f"{size:.2f} MB", U.TEXT_DIM)
        y += p(92)
        self.group(y, p(84), tr("Настройки и правила"))
        self.label(self.x0 + p(14), y + p(38), tr("Файл со всеми настройками и правилами, кроме пути к базе и положения окна."), U.TEXT_DIM)
        self.button(self.x0 + p(12), y + p(50), bw, tr("Экспорт в файл"), self._export)
        self.button(self.x0 + p(12) + bw + p(8), y + p(50), bw, tr("Импорт из файла"), self._import)
        y += p(92)
        self.group(y, p(66), tr("Папка программы"))
        self.button(self.x0 + p(12), y + p(30), bw, tr("Открыть папку"), lambda: app._open(s.folder))
        self.label(self.x0 + p(12) + bw + p(12), y + p(43), self.t.fit(s.folder, self.x1 - self.x0 - bw - p(40), middle=True), U.TEXT_DIM)
        y += p(74)
        self.group(y, p(66), tr("Обновления"))
        self.update_btn = self.button(self.x0 + p(12), y + p(30), bw, tr("Проверить обновления"), app.check_updates)
        self.label(self.x0 + p(12) + bw + p(12), y + p(43), tr("Версия {version}").format(version=U.VERSION) + ". " + tr("Единственное обращение программы к сети, только по этой кнопке."), U.TEXT_DIM)
        y += p(74)
        self.group(y, p(58), tr("Модификации"))
        self.led(self.x0 + p(14), y + p(38), tr("Использовать сторонние модификации"), "mods_enabled", "", lambda: app.root.after(1, app.mods_switch))

    def _show_log(self) -> None:
        """Окно журнала действий."""
        log = self.app.s.log
        dialog = U.Dialog(self.app.root, self.t, tr("Журнал действий"), "", [tr("Открыть файл"), tr("Закрыть")], width=820, text_view=log.tail() or tr("Пока пусто."))
        if dialog.result == 0 and os.path.exists(log.path):
            self.app._open(log.path)

    def _export(self) -> None:
        """Экспорт настроек в файл."""
        path = filedialog.asksaveasfilename(parent=self.app.root, title=tr("Экспорт в файл"), defaultextension=".json", initialfile="FODB-settings.json", filetypes=[("JSON", "*.json")])
        if path:
            try:
                self.app._save_layout()
                self.app.s.export_to(path)
                self.app.set_hint(tr("Настройки сохранены: {name}").format(name=os.path.basename(path)))
                self.app.s.log.write("export", path)
            except OSError as exc:
                U.Dialog(self.app.root, self.t, tr("Ошибка"), str(exc), [tr("Понятно")])

    def _import(self) -> None:
        """Импорт настроек из файла."""
        path = filedialog.askopenfilename(parent=self.app.root, title=tr("Импорт из файла"), filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            self.app.s.import_from(path)
        except (OSError, ValueError) as exc:
            U.Dialog(self.app.root, self.t, tr("Ошибка"), str(exc), [tr("Понятно")])
            return
        self.app.s.log.write("import", path)
        self.app.settings_imported()


class Tutorial:
    """Обучение: затемняет окно, подсвечивает его часть и объясняет её в карточке рядом."""

    DIM = 0.6  # насколько темнеет окно вокруг подсветки
    MOVE_MS = 280

    def __init__(self, app, done=None):
        """done: что выполнить, когда обучение закончится."""
        self.app, self.t, self.done = app, app.t, done
        self.root = app.root
        p = self.t.p
        app.show_tab("plugins")
        app.show_page("options")
        self.root.update_idletasks()
        box_of = self._canvas_box
        self.steps = (
            ("Добро пожаловать в FODB", "FODB наводит порядок в браузере плагинов FL Studio. Короткая экскурсия покажет главное, это займёт минуту.", None),
            ("Список плагинов", "Здесь все плагины из базы FL Studio. Назначение определяется автоматически. Звезда значит, что плагин уже разложен: клик по ней кладёт или убирает его.",
             lambda: self._widget_box(app.grid.c)),
            ("Источники плагинов", "Откуда брать плагины. Снимите галочку, чтобы скрыть источник, например VST, если есть VST3.", lambda: box_of(app.left, app.src_box)),
            ("Раскладка папок", "Как называть папки: по производителю, по назначению или вложенно. Для эффектов и генераторов можно выбрать разное.", lambda: box_of(app.left, app.layout_box)),
            ("Параметры организации", "Что делать при раскладке: одна копия на плагин, пропуск ошибок и другие правила. Наведите на строку, и внизу появится подсказка.", lambda: box_of(app.left, app.options_box)),
            ("Фильтры", "Воронка открывает фильтры по назначению, производителю и другим признакам. В поиске можно просто набрать название.", self._filter_box),
            ("Организовать плагины", "Главная кнопка. Сначала покажет, что и куда ляжет, и сделает бэкап базы. Ваши плагины при этом не меняются.",
             lambda: box_of(app.left, app.left.bbox(app.main_btn.image))),
            ("Настройки", "Здесь отмена и бэкапы, цвета и шрифт, горячие клавиши и ваши правила.", lambda: box_of(app.tabs, app.tabs.bbox("win_settings"))),
            ("Всё готово!", "После раскладки обновите браузер плагинов в FL Studio. Знак вопроса покажет эту экскурсию снова, а планета откроет справку.", self._help_box),
        )
        self.index = 0
        self.size = (self.root.winfo_rootx(), self.root.winfo_rooty(), self.root.winfo_width(), self.root.winfo_height())
        rx, ry, rw, rh = self.size
        owner = U.hwnd_of(self.root)
        self.shade = U.Curtain("FODBTutorialShade")
        self.ring = U.Curtain("FODBTutorialRing")
        self.ring_width = max(2, p(2))
        self.shade.show(owner, rx, ry, rw, rh, "#000000")
        self.ring.show(owner, rx, ry, rw, rh, U.ORANGE)
        self.ring.shape((0, 0, 0, 0), None)
        self.hole = None
        self.shade.alpha(0.0)
        self.top = tk.Toplevel(self.root, bg=U.EDGE)
        self.top.withdraw()
        self.top.overrideredirect(True)
        self.top.transient(self.root)  # карточка принадлежит окну и не висит поверх других программ
        self.top.protocol("WM_DELETE_WINDOW", self.finish)
        self.card_w = p(380)
        self.c = tk.Canvas(self.top, bg=U.PANEL, width=self.card_w, height=p(180), highlightthickness=1, highlightbackground=U.ORANGE, bd=0)
        self.c.pack()
        self.top.bind("<Escape>", lambda e: self.finish())
        self.top.bind("<Return>", lambda e: self.next())
        self.top.bind("<KeyPress>", self._key)
        self._build_card()
        U.fade_in_window(self.top, self.t.motion, 200)
        self.t.motion.run("tutorial_shade", 220, lambda share: self.shade.alpha(self.DIM * share))
        self.draw()
        self.card_x, self.card_y = self._card_position(None)
        self.top.geometry(f"+{self.card_x}+{self.card_y}")
        self.top.deiconify()
        self.top.lift()
        self.top.focus_force()
        self.top.grab_set()

    # ------------------------------------------------------------------ где что находится
    def _widget_box(self, widget) -> tuple[int, int, int, int]:
        """Границы виджета на экране."""
        x, y = widget.winfo_rootx(), widget.winfo_rooty()
        return x, y, x + widget.winfo_width(), y + widget.winfo_height()

    def _canvas_box(self, canvas, box) -> tuple[int, int, int, int]:
        """Границы прямоугольника с холста на экране."""
        x, y = canvas.winfo_rootx(), canvas.winfo_rooty()
        return x + box[0], y + box[1], x + box[2], y + box[3]

    def _filter_box(self) -> tuple[int, int, int, int]:
        """Значок фильтров и поле поиска."""
        app = self.app
        x, y = app.bottom.winfo_rootx(), app.bottom.winfo_rooty()
        left = app.bottom.bbox(app.filter_btn.hit)[0]
        return x + left, y, x + app.bottom.winfo_width(), y + app.bottom.winfo_height()

    def _help_box(self) -> tuple[int, int, int, int]:
        """Значки обучения и справки."""
        app = self.app
        x, y = app.tabs.winfo_rootx(), app.tabs.winfo_rooty()
        x0, y0, _x1, y1 = app.tabs.bbox(app.wiki_btn.hit)
        return x + x0, y + y0, x + app.tabs.bbox(app.help_btn.hit)[2], y + y1

    def _target(self):
        """Что подсвечивает текущий шаг, с небольшим запасом вокруг. None: ничего."""
        getter = self.steps[self.index][2]
        if getter is None:
            return None
        pad = self.t.p(3)
        x0, y0, x1, y1 = getter()
        return x0 - pad, y0 - pad, x1 + pad, y1 + pad

    def _card_position(self, target) -> tuple[int, int]:
        """Ставит карточку там, где хватает места: справа, слева, снизу или сверху от подсветки."""
        p = self.t.p
        rx, ry, rw, rh = self.size
        w, h = self.card_w + 2, self.c.winfo_reqheight() + 2
        if target is None:
            return rx + (rw - w) // 2, ry + (rh - h) // 2
        x0, y0, x1, y1 = target
        gap = p(14)
        middle_x, middle_y = (x0 + x1 - w) // 2, (y0 + y1 - h) // 2
        options = ((x1 + gap, middle_y, x1 + gap + w <= rx + rw), (x0 - gap - w, middle_y, x0 - gap - w >= rx),
                   (middle_x, y1 + gap, y1 + gap + h <= ry + rh), (middle_x, y0 - gap - h, y0 - gap - h >= ry))
        x, y = next(((x, y) for x, y, fits in options if fits), (rx + (rw - w) // 2, ry + p(40)))
        return max(rx + p(6), min(rx + rw - w - p(6), x)), max(ry + p(6), min(ry + rh - h - p(6), y))

    # ------------------------------------------------------------------ карточка
    def _build_card(self) -> None:
        """Создаёт карточку один раз. Её высота равна самому длинному шагу, поэтому значки не прыгают."""
        c, t = self.c, self.t
        p = t.p
        self.title_item = c.create_text(p(16), p(20), anchor="w", fill=U.ORANGE, font=t.font_title)
        self.body_item = c.create_text(p(16), p(38), anchor="nw", fill=U.TEXT, font=t.font, width=self.card_w - p(32))
        bottom = 0
        for _title, text, _getter in self.steps:
            c.itemconfigure(self.body_item, text=tr(text))
            bottom = max(bottom, c.bbox(self.body_item)[3])
        y = bottom + p(26)
        self.skip_item = c.create_text(p(16), y, text=tr("Пропустить"), anchor="w", fill=U.TEXT_SOFT, font=t.font)
        c.tag_bind(self.skip_item, "<Enter>", lambda e: c.itemconfigure(self.skip_item, fill=U.ORANGE))
        c.tag_bind(self.skip_item, "<Leave>", lambda e: c.itemconfigure(self.skip_item, fill=U.TEXT_SOFT))
        c.tag_bind(self.skip_item, "<ButtonRelease-1>", lambda e: self.finish())
        self.count_item = c.create_text(self.card_w // 2, y, fill=U.TEXT_DIM, font=t.font)
        self.back_btn = U.IconButton(c, t, self.card_w - p(58), y, "ic_prev", self.back)
        self.next_btn = U.IconButton(c, t, self.card_w - p(28), y, "ic_next", self.next)
        c.configure(height=y + p(20))

    def draw(self) -> None:
        """Показывает в карточке текущий шаг."""
        c = self.c
        title, text, _getter = self.steps[self.index]
        last = self.index == len(self.steps) - 1
        c.itemconfigure(self.title_item, text=tr(title))
        c.itemconfigure(self.body_item, text=tr(text))
        c.itemconfigure(self.count_item, text=f"{self.index + 1} / {len(self.steps)}")
        c.itemconfigure(self.skip_item, state="hidden" if last else "normal")
        self.back_btn.set_visible(self.index > 0)
        self.next_btn.set_icon("ic_done" if last else "ic_next")
        self.top.update_idletasks()

    def _key(self, event) -> None:
        """Стрелки листают шаги. Коды клавиш не зависят от раскладки."""
        if event.keycode == 39:
            self.next()
        elif event.keycode == 37:
            self.back()

    def next(self) -> None:
        """Следующий шаг или конец."""
        if self.index == len(self.steps) - 1:
            self.finish()
        else:
            self.go(self.index + 1)

    def back(self) -> None:
        """Предыдущий шаг."""
        if self.index:
            self.go(self.index - 1)

    def go(self, index: int) -> None:
        """Переход: подсветка и карточка плавно едут на новое место."""
        self.index = index
        self.draw()
        target = self._target()
        rx, ry, rw, rh = self.size
        cx, cy = rx + rw // 2, ry + rh // 2
        start_hole = self.hole or (cx, cy, cx, cy)
        end_hole = target or (cx, cy, cx, cy)
        start_card = (self.card_x, self.card_y)
        end_card = self._card_position(target)

        def step(share):
            eased = 1 - (1 - share) ** 3
            box = tuple(round(a + (b - a) * eased) for a, b in zip(start_hole, end_hole))
            self._set_hole(box)
            self.card_x = round(start_card[0] + (end_card[0] - start_card[0]) * eased)
            self.card_y = round(start_card[1] + (end_card[1] - start_card[1]) * eased)
            self.top.geometry(f"+{self.card_x}+{self.card_y}")

        def arrive():
            if target is None:
                self.hole = None
                self.shade.shape(None, None)
                self.ring.shape((0, 0, 0, 0), None)

        self.t.motion.run("tutorial_move", self.MOVE_MS, step, arrive)

    def _set_hole(self, box) -> None:
        """Прорезает затемнение и обводит прорезь."""
        rx, ry, rw, rh = self.size
        self.hole = box  # следующий переход начнётся отсюда, даже если этот не закончился
        x0, y0, x1, y1 = box[0] - rx, box[1] - ry, box[2] - rx, box[3] - ry
        self.shade.shape((0, 0, rw, rh), (x0, y0, x1, y1))
        w = self.ring_width
        self.ring.shape((x0 - w, y0 - w, x1 + w, y1 + w), (x0, y0, x1, y1))

    def finish(self) -> None:
        """Конец обучения: всё плавно исчезает, окно снова отвечает."""
        self.t.motion.stop("tutorial_move")
        self.top.grab_release()
        self.top.destroy()
        self.ring.hide()
        self.t.motion.run("tutorial_shade", 200, lambda share: self.shade.alpha(self.DIM * (1 - share)), self.shade.hide)
        self.root.focus_force()
        if self.done:
            self.done()


class Wizard:
    """Первый запуск: только то, что программа не может решить сама."""

    def __init__(self, app):
        """Показывает окно и ждёт его закрытия."""
        self.app = app
        self.top = tk.Toplevel(app.root, bg=U.EDGE)
        self.top.withdraw()
        self.top.overrideredirect(True)
        self.c = None
        self.draw()
        self.top.bind("<Escape>", lambda e: self.done())
        self.top.deiconify()
        self.top.lift()
        self.top.focus_force()
        self.top.grab_set()
        app.root.wait_window(self.top)

    def draw(self) -> None:
        """Рисует окно заново (после смены языка или масштаба)."""
        app, t = self.app, self.app.t
        p = t.p
        if self.c:
            self.c.destroy()
        self.t = t
        w, h = p(620), p(292)
        c = self.c = tk.Canvas(self.top, bg=U.PANEL, width=w, height=h, highlightthickness=1, highlightbackground=U.FRAME, bd=0)
        c.pack()
        c.create_rectangle(0, 0, w, p(40), fill=U.FRAME, outline="")
        c.create_text(p(14), p(20), text=tr("Первый запуск"), anchor="w", fill=U.TITLE_TEXT, font=t.font_title)
        c.create_text(p(16), p(60), text=tr("Всё остальное можно поменять позже на вкладке «Настройки»."), anchor="w", fill=U.TEXT_DIM, font=t.font)
        x = p(190)
        field_w = w - x - p(16)
        c.create_text(p(16), p(99), text=tr("Язык"), anchor="w", fill=U.TEXT_SOFT, font=t.font_bold)
        U.Button(c, t, x, p(86), field_w, p(26), i18n.available().get(i18n.LANG, i18n.LANG), self.language_menu)
        c.create_image(x + field_w - p(12), p(99), image=t.images["caret"], state="disabled")
        c.create_text(p(16), p(145), text=tr("База плагинов FL Studio"), anchor="w", fill=U.TEXT_SOFT, font=t.font_bold)
        U.IconButton(c, t, x + p(17), p(145), "folder", self.choose, U.PANEL)
        found = app.db or tr("Папка не найдена: выберите её")
        c.create_text(x + p(44), p(137), text=t.fit(found, field_w - p(46), middle=True), anchor="w", fill=U.TEXT if app.db else U.ORANGE, font=t.font)
        c.create_text(x + p(44), p(152), text=tr("Найдена автоматически. Можно указать другую.") if app.db else "", anchor="w", fill=U.TEXT_DIM, font=t.font)
        c.create_text(p(16), p(195), text=tr("Масштаб интерфейса"), anchor="w", fill=U.TEXT_SOFT, font=t.font_bold)
        Slider(c, t, x + p(6), p(195), field_w - p(70), 75, 200, app.s["ui_scale"], "{value} %", self.scale, under=U.PANEL)
        U.Button(c, t, w - p(136), h - p(44), p(120), p(28), tr("Готово"), self.done)
        self.top.update_idletasks()
        root = app.root
        self.top.geometry(f"{w + 2}x{h + 2}+{root.winfo_rootx() + (root.winfo_width() - w) // 2}+{root.winfo_rooty() + (root.winfo_height() - h) // 2}")

    def language_menu(self) -> None:
        """Меню языков."""
        menu = self.app._menu()
        for code, name in i18n.available().items():
            menu.add_command(label=name, command=lambda v=code: self.language(v))
        menu.popup(self.top.winfo_pointerx(), self.top.winfo_pointery())

    def language(self, code: str) -> None:
        """Меняет язык."""
        self.app.set_language(code)
        self.draw()

    def choose(self) -> None:
        """Выбор папки базы."""
        self.app.choose_database()
        self.draw()

    def scale(self, percent: int) -> None:
        """Меняет масштаб."""
        self.app.set_scale(percent)
        self.draw()

    def done(self) -> None:
        """Сохраняет настройки и закрывает окно."""
        self.app.s.save()
        self.top.grab_release()
        self.top.destroy()
