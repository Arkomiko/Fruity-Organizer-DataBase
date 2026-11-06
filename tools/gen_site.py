"""Создаёт сайт для GitHub Pages в папке GiDo: главную и вики на всех языках проекта.

Тексты берутся из docs_text.py и language/*.json, поэтому отдельно переводить сайт не нужно.
Запуск: python tools/gen_site.py
"""
import json
import os
import sys
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import hotkeys  # noqa: E402
import rules  # noqa: E402
from docs_text import LANGUAGES  # noqa: E402
from gen_docs import EXAMPLE, QUERY, RULES, TOKENS, write  # noqa: E402

REPO = "https://github.com/Arkomiko/Fruity-Organizer-DataBase"
# Страницы вики: адрес файла и заголовок (ключ из docs_text.py или строка интерфейса).
WIKI = (("start", "quick"), ("layouts", "layouts"), ("filters", "filters"), ("rules", "advanced"), ("safety", "safety"),
        ("themes", "themes"), ("settings", "Настройки"), ("hotkeys", "Горячие клавиши"), ("build", "build"))
# Подписи из интерфейса программы: уже переведены на все языки.
OPTIONS = (
    ("Одна копия плагина", "Если плагин есть в нескольких форматах, копируется один. Порядок форматов задаётся в настройках."),
    ("Пропускать плагины с ошибками", "Не копировать плагины, которые FL Studio не смог просканировать."),
    ("Пропускать уже организованные", "Плагин со звездой уже лежит в Effects или Generators: повторно он не копируется."),
    ("Перекладывать уже организованные", "Переместить плагины со звездой в папки текущей раскладки. Отменяется кнопкой «Отменить»."),
    ("Перезаписывать существующие файлы", "Заменять файл, если такой уже есть в папке вендора."),
    ("Только плагины из списка", "Организовать только то, что видно в списке с учётом фильтров и поиска."),
    ("Переносить из папки New", "После раскладки плагин исчезает из списка New в FL Studio. Кнопка «Отменить» вернёт его обратно."),
)
FILTER_GROUPS = ("Тип", "Формат", "Разрядность", "Статус", "Организация", "Форматов у плагина", "Дата файла", "Размер файла",
                 "Как определено назначение", "Назначение", "Производитель")
SETTINGS = (
    ("Общие", ("Язык", "При запуске", "Кнопка закрытия", "Двойной клик по плагину", "Поверх всех окон", "База плагинов FL Studio")),
    ("Раскладка", ("Раскладка папок", "Язык папок назначения", "Убирать LLC, GmbH, Inc. из названий папок", "Переносить из папки New",
                   "Порядок форматов для одной копии")),
    ("Производители", ("Заменяет название производителя в списке и в папках. Например, Direct на MiniMeters.",)),
    ("Правила", ("Первое подошедшее правило важнее автоматики. В условиях работают регулярные выражения.",)),
    ("Бэкапы", ("Бэкап перед каждым изменением", "Хранить бэкапов", "Спрашивать подтверждение")),
    ("Оформление", ("Цветовая тема", "Масштаб интерфейса", "Шрифт", "Размер шрифта", "Мягкие переходы и анимация", "Колонки списка")),
    ("Клавиши", ("Дважды щёлкните строку, чтобы назначить другое сочетание.",)),
    ("Данные", ("Журнал действий", "Экспорт в файл", "Импорт из файла", "Проверить обновления")),
)
STYLE = """:root{color-scheme:dark;--back:#2b3136;--panel:#3c454b;--line:#273036;--text:#d5dbdf;--dim:#9aa4aa;--accent:#ffb23e}
*{box-sizing:border-box}
body{margin:0;background:var(--back);color:var(--text);font:16px/1.6 "Segoe UI",system-ui,sans-serif}
a{color:var(--accent)}
img{max-width:100%;height:auto;display:block}
header{background:#262b2f;border-bottom:1px solid var(--line)}
.bar,main,footer{max-width:960px;margin:0 auto;padding:0 16px}
.bar{display:flex;flex-wrap:wrap;align-items:center;gap:6px 18px;padding-block:10px}
.bar .name{font-weight:600;color:var(--text);text-decoration:none;margin-inline-end:auto}
.bar a{text-decoration:none}
.langs{position:relative}
.langs summary{cursor:pointer;color:var(--dim)}
.langs ul{position:absolute;inset-inline-end:0;z-index:1;width:min(520px,90vw);margin:6px 0 0;padding:10px;list-style:none;columns:2;background:var(--panel);border:1px solid var(--line);border-radius:4px}
main{padding-block:24px 40px}
h1{font-size:28px;line-height:1.25;margin:0 0 12px}
h2{font-size:20px;margin:28px 0 8px}
.lead{color:var(--dim);margin-top:0}
.download{display:inline-block;margin:6px 0 22px;padding:9px 18px;background:var(--accent);color:#1a1d20;border-radius:4px;font-weight:600;text-decoration:none}
.shot{border:1px solid var(--line);border-radius:4px;margin-bottom:12px}
pre{direction:ltr;text-align:left;overflow-x:auto;padding:12px;background:#262b2f;border:1px solid var(--line);border-radius:4px;font:14px/1.5 Consolas,monospace}
table{border-collapse:collapse;width:100%}
td,th{padding:6px 10px;border:1px solid var(--line);text-align:start}
th{background:var(--panel);font-weight:600}
.wiki{display:grid;grid-template-columns:220px 1fr;gap:28px}
.wiki nav ul{list-style:none;margin:0;padding:0}
.wiki nav li{margin-bottom:6px}
.wiki nav .here{color:var(--text);font-weight:600}
.page{min-width:0}
footer{padding-block:16px 28px;color:var(--dim);font-size:14px;border-top:1px solid var(--line)}
@media (max-width:720px){.wiki{grid-template-columns:1fr}.langs ul{columns:1;inset-inline:0 auto}}
"""


def table_of(code: str) -> dict:
    """Строки интерфейса на этом языке."""
    with open(os.path.join(ROOT, "language", code + ".json"), encoding="utf-8") as f:
        return json.load(f)


class Site:
    """Страницы одного языка. prefix: путь от текущей страницы до корня сайта."""

    def __init__(self, code: str, out: str):
        self.code, self.lang, self.out = code, LANGUAGES[code], out
        self.table = table_of(code)

    def tr(self, key: str) -> str:
        """Строка интерфейса в виде безопасного HTML. Нет ключа: ошибка, а не молчаливый пропуск."""
        return escape(self.table[key].strip())

    def text(self, key: str) -> str:
        """Строка из docs_text.py в виде безопасного HTML."""
        return escape(self.lang[key])

    def title(self, key: str) -> str:
        """Заголовок страницы вики."""
        return self.text(key) if key in self.lang else self.tr(key)

    def link(self, prefix: str, slug: str | None, code: str | None = None) -> str:
        """Адрес страницы: None это главная, wiki это содержание вики, иначе страница вики."""
        folder = f"{prefix}{code or self.code}/"
        if slug is None:
            return folder + "index.html"
        return folder + ("wiki/index.html" if slug == "wiki" else f"wiki/{slug}.html")

    def shell(self, prefix: str, slug: str | None, heading: str, body: str) -> str:
        """Общая оболочка: шапка, выбор языка и подвал."""
        lang = self.lang
        direction = ' dir="rtl"' if lang.get("rtl") else ""
        choices = "".join(f'<li><a href="{self.link(prefix, slug, code)}" lang="{other["html"]}">{escape(other["name"])}</a></li>'
                          for code, other in LANGUAGES.items())
        return f'''<!doctype html>
<html lang="{lang["html"]}"{direction}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{heading} | FODB</title>
<meta name="description" content="{self.text("intro")}">
<link rel="stylesheet" href="{prefix}site.css">
</head>
<body>
<header><div class="bar">
<a class="name" href="{self.link(prefix, None)}">FODB</a>
<a href="{self.link(prefix, None)}">{self.text("home")}</a>
<a href="{self.link(prefix, "wiki")}">{self.text("wiki")}</a>
<a href="{REPO}/releases/latest">{self.text("download")}</a>
<a href="{REPO}">{self.text("source")}</a>
<details class="langs"><summary>{self.tr("Язык")}: {escape(lang["name"])}</summary><ul>{choices}</ul></details>
</div></header>
<main>
{body}
</main>
<footer><p>{self.text("credits_t")}</p><p>{self.text("disclaimer")}</p></footer>
</body>
</html>
'''

    def home(self, prefix: str) -> str:
        """Главная страница."""
        lang = self.lang
        demo = "demo-ru.gif" if self.code in ("RU-ru", "UK-ua", "BE-by", "KK-kz") else "demo-en.gif"
        features = "".join(f"<li>{self.text(f'f{i}')}</li>" for i in range(1, 8))
        steps = "".join(f"<li>{self.text(f'q{i}')}</li>" for i in range(1, 4))
        pages = "".join(f'<li><a href="{self.link(prefix, slug)}">{self.title(key)}</a></li>' for slug, key in WIKI)
        body = f'''<img class="logo" src="{prefix}logo.svg" alt="FODB" width="240">
<h1>{escape(lang["taglines"][0])}</h1>
<p class="lead">{self.text("intro")}</p>
<a class="download" href="{REPO}/releases/latest">{self.text("download")}</a>
<img class="shot" src="{prefix}{demo}" alt="FODB">
<h2>{self.text("features")}</h2>
<ul>{features}</ul>
<h2>{self.text("quick")}</h2>
<ol>{steps}</ol>
<h2>{self.text("wiki")}</h2>
<ul>{pages}</ul>'''
        return self.shell(prefix, None, "Fruity Organizer DataBase", body)

    def wiki_body(self, slug: str) -> str:
        """Содержимое одной страницы вики."""
        tr, text = self.tr, self.text
        items = lambda values: "<ul>" + "".join(f"<li>{v}</li>" for v in values) + "</ul>"  # noqa: E731
        if slug == "start":
            steps = "".join(f"<li>{text(f'q{i}')}</li>" for i in range(1, 4))
            return f'<ol>{steps}</ol><p>{tr("Всё остальное можно поменять позже на вкладке «Настройки».")}</p>'
        if slug == "layouts":
            presets = items(tr(label) for label in rules.LAYOUT_LABELS.values())
            options = "".join(f"<li><b>{tr(name)}</b>: {tr(hint)}</li>" for name, hint in OPTIONS)
            return (f'<p>{text("layouts_t")}</p><pre>{escape(TOKENS)}\n\n{escape(EXAMPLE)}</pre>{presets}'
                    f'<h2>{tr("Параметры организации")}</h2><ul>{options}</ul>')
        if slug == "filters":
            return (f'<p>{text("filters_t")}</p><pre>{escape(QUERY)}</pre><h2>{tr("Фильтры")}</h2>'
                    + items(tr(group) for group in FILTER_GROUPS))
        if slug == "rules":
            purposes = sorted(self.table[label] for label in rules.PURPOSES.values())
            return (f'<p>{text("f2")}</p><p>{text("advanced_t")}</p><pre>{escape(RULES)}</pre><p>'
                    f'{tr("Первое подошедшее правило важнее автоматики. В условиях работают регулярные выражения.")}</p>'
                    f'<h2>{tr("Назначение")}</h2>' + items(escape(p) for p in purposes))
        if slug == "safety":
            return items(text(f"s{i}") for i in range(1, 4)) + (
                f'<h2>{tr("Журнал действий")}</h2><p>{tr("Что, куда и когда скопировано. Старые записи перезаписываются после 20 МБ.")}</p>')
        if slug == "themes":
            return (f'<p>{text("themes_t")}</p>' + items(tr(mode) for mode in ("Классика", "Как в моей FL", "Свои"))
                    + items(tr(name) for name in ("Масштаб интерфейса", "Шрифт", "Размер шрифта", "Мягкие переходы и анимация")))
        if slug == "settings":
            return "".join(f"<h2>{tr(section)}</h2>" + items(tr(entry) for entry in entries) for section, entries in SETTINGS)
        if slug == "hotkeys":
            rows = "".join(f'<tr><td>{tr(label)}</td><td dir="ltr">{default}</td></tr>' for _action, label, default in hotkeys.ACTIONS)
            return (f'<p>{tr("Дважды щёлкните строку, чтобы назначить другое сочетание.")}</p>'
                    f'<table><tr><th>{tr("Действие")}</th><th>{tr("Клавиши")}</th></tr>{rows}</table>')
        return f"<p>{text('build_t')}</p><pre>./build.ps1</pre>"

    def wiki_page(self, prefix: str, slug: str, key: str | None) -> str:
        """Страница вики с боковым содержанием. key=None: само содержание."""
        heading = self.title(key) if key else self.text("wiki")
        entries = "".join(
            f'<li><span class="here">{self.title(k)}</span></li>' if s == slug else f'<li><a href="{self.link(prefix, s)}">{self.title(k)}</a></li>'
            for s, k in WIKI)
        content = self.wiki_body(slug) if key else "<ul>" + "".join(
            f'<li><a href="{self.link(prefix, s)}">{self.title(k)}</a></li>' for s, k in WIKI) + "</ul>"
        body = f'<div class="wiki"><nav><ul>{entries}</ul></nav><div class="page"><h1>{heading}</h1>{content}</div></div>'
        return self.shell(prefix, "wiki" if not key else slug, heading, body)

    def build(self) -> None:
        """Записывает все страницы этого языка."""
        folder = os.path.join(self.out, self.code)
        write(os.path.join(folder, "index.html"), self.home("../"))
        write(os.path.join(folder, "wiki", "index.html"), self.wiki_page("../../", "wiki", None))
        for slug, key in WIKI:
            write(os.path.join(folder, "wiki", slug + ".html"), self.wiki_page("../../", slug, key))


def main(out: str = os.path.join(ROOT, "GiDo")) -> int:
    """Создаёт сайт и возвращает число языков."""
    write(os.path.join(out, "site.css"), STYLE)
    for code in LANGUAGES:
        Site(code, out).build()
    write(os.path.join(out, "index.html"), Site("EN-en", out).home(""))
    return len(LANGUAGES)


if __name__ == "__main__":
    print("languages:", main())
