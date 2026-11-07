"""Preview Tree: предпросмотр раскладки деревом с перетаскиванием плагинов."""
import os
import tkinter as tk

from i18n import tr
import ui

TITLE = {"EN-en": "Preview Tree", "RU-ru": "Дерево предпросмотра"}
HELP = {"EN-en": "Drag plugins between folders. Click a folder to collapse it.", "RU-ru": "Перетаскивайте плагины между папками. Щелчок по папке сворачивает её."}


class PreviewTree:
    """Окно дерева. После закрытия result показывает, надо ли организовать."""

    def __init__(self, api, plan, header):
        self.api, self.plan = api, plan
        self.db = api.app.db
        self.t = api.app.t
        self.collapsed = set()
        self.rows = []
        self.result = False
        self.drag = None
        self.target = None
        root = api.app.root
        p = self.t.p
        width, height = p(760), min(p(620), root.winfo_height() - p(40))
        top = self.top = tk.Toplevel(root, bg=ui.EDGE)
        top.withdraw()
        top.overrideredirect(True)
        top.attributes("-topmost", bool(root.attributes("-topmost")))
        head = tk.Canvas(top, bg=ui.FRAME, width=width, height=p(28), highlightthickness=0)
        head.pack(fill="x", padx=1, pady=(1, 0))
        head.create_text(p(10), p(14), text=api.text(TITLE), anchor="w", fill=ui.TITLE_TEXT, font=self.t.font_title)
        info = tk.Canvas(top, bg=ui.PANEL, width=width, highlightthickness=0)
        text = info.create_text(p(12), p(8), text=header + "\n" + api.text(HELP), anchor="nw", fill=ui.TEXT, font=self.t.font, width=width - p(24))
        info.configure(height=info.bbox(text)[3] + p(8))
        info.pack(fill="x", padx=1)
        self.row_h = self.t.font.metrics("linespace") + p(5)
        self.c = tk.Canvas(top, bg=ui.ROW_A, width=width, highlightthickness=0)
        self.c.pack(fill="both", expand=True, padx=1)
        foot = tk.Canvas(top, bg=ui.PANEL, width=width, height=p(44), highlightthickness=0)
        foot.pack(fill="x", padx=1, pady=(0, 1))
        ui.Button(foot, self.t, width - p(250), p(8), p(120), p(28), tr("Организовать"), lambda: self.close(True))
        ui.Button(foot, self.t, width - p(124), p(8), p(112), p(28), tr("Отмена"), lambda: self.close(False))
        self.c.bind("<ButtonPress-1>", self.press)
        self.c.bind("<B1-Motion>", self.move)
        self.c.bind("<ButtonRelease-1>", self.release)
        self.c.bind("<MouseWheel>", lambda e: self.c.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        top.bind("<Escape>", lambda e: self.close(False))
        self.c.configure(yscrollincrement=self.row_h)
        x = root.winfo_rootx() + (root.winfo_width() - width) // 2
        y = root.winfo_rooty() + (root.winfo_height() - height) // 2
        top.geometry(f"{width + 2}x{height}+{x}+{y}")
        self.draw()
        top.deiconify()
        top.lift()
        top.focus_force()
        top.grab_set()
        root.wait_window(top)

    def close(self, result):
        """Закрывает окно с ответом."""
        self.result = result
        self.top.destroy()

    def relative(self, action):
        """Путь папки действия от корня базы."""
        return os.path.relpath(action.dest_dir, self.db)

    def build_rows(self):
        """Плоский список строк дерева: папки с отступом и плагины под ними."""
        content = {}
        for action in self.plan.actions:
            content.setdefault(self.relative(action), []).append(action)
        nodes = {}
        for path, actions in content.items():
            parts = path.split(os.sep)
            for depth in range(len(parts)):
                prefix = os.sep.join(parts[:depth + 1])
                nodes[prefix] = nodes.get(prefix, 0) + len(actions)
        rows = []
        for path in sorted(nodes, key=lambda item: [part.casefold() for part in item.split(os.sep)]):
            parts = path.split(os.sep)
            if any(os.sep.join(parts[:depth]) in self.collapsed for depth in range(1, len(parts))):
                continue
            rows.append({"folder": path, "depth": len(parts) - 1, "name": parts[-1], "count": nodes[path]})
            if path not in self.collapsed:
                for action in sorted(content.get(path, ()), key=lambda a: a.plugin.name.casefold()):
                    rows.append({"action": action, "folder": path, "depth": len(parts), "name": action.plugin.name})
        self.rows = rows

    def draw(self):
        """Рисует дерево."""
        c, t = self.c, self.t
        p = t.p
        c.delete("all")
        self.build_rows()
        width = int(c["width"])
        for index, row in enumerate(self.rows):
            y = index * self.row_h
            is_folder = "action" not in row
            fill = ui.ROW_B if index % 2 else ui.ROW_A
            if is_folder and row["folder"] == self.target:
                fill = ui.SELECT
            c.create_rectangle(0, y, width, y + self.row_h, fill=fill, outline="")
            x = p(10) + row["depth"] * p(16)
            if is_folder:
                arrow = "\u25b8" if row["folder"] in self.collapsed else "\u25be"
                label = f"{arrow}  {row['name']}  ({row['count']})"
                c.create_text(x, y + self.row_h // 2, text=label, anchor="w", fill=ui.ORANGE if fill != ui.SELECT else ui.WHITE, font=t.font_bold)
            else:
                c.create_text(x + p(4), y + self.row_h // 2, text=row["name"], anchor="w", fill=ui.TEXT, font=t.font)
        c.configure(scrollregion=(0, 0, width, len(self.rows) * self.row_h))

    def row_at(self, event):
        """Строка под мышью."""
        index = int(self.c.canvasy(event.y) // self.row_h)
        return self.rows[index] if 0 <= index < len(self.rows) else None

    def press(self, event):
        """Плагин можно взять, папку можно свернуть при отпускании."""
        row = self.row_at(event)
        self.pressed = row
        self.drag = row["action"] if row and "action" in row else None
        self.ghost = None

    def move(self, event):
        """Тянем плагин: рядом с мышью его имя, папка под мышью подсвечена."""
        if not self.drag:
            return
        if event.y < self.row_h:
            self.c.yview_scroll(-1, "units")
        elif event.y > self.c.winfo_height() - self.row_h:
            self.c.yview_scroll(1, "units")
        row = self.row_at(event)
        target = row["folder"] if row else None
        if target != self.target:
            self.target = target if target and self.allowed(target) else None
            self.draw()
            self.ghost = None
        x, y = self.c.canvasx(event.x) + self.t.p(14), self.c.canvasy(event.y)
        if self.ghost is None:
            self.ghost = self.c.create_text(x, y, text=self.drag.plugin.name, anchor="w", fill=ui.WHITE, font=self.t.font_bold)
        else:
            self.c.coords(self.ghost, x, y)

    def allowed(self, folder):
        """Эффекты и генераторы лежат в разных корнях: между ними переносить нельзя."""
        return folder.split(os.sep)[0] == self.relative(self.drag).split(os.sep)[0]

    def release(self, event):
        """Отпустили: переносим плагин или сворачиваем папку."""
        row = self.row_at(event)
        if self.drag:
            if self.target and self.target != self.relative(self.drag):
                self.drag.dest_dir = os.path.join(self.db, self.target)
        elif row and row is self.pressed and "action" not in row:
            self.collapsed.symmetric_difference_update({row["folder"]})
        self.drag = self.target = None
        self.draw()


def activate(api):
    """Подменяет окно предпросмотра."""
    api.set_preview(lambda plan, header: PreviewTree(api, plan, header).result)
