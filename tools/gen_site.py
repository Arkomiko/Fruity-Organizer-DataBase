"""Создаёт сайт для GitHub Pages в папке GiDo: главную и вики на всех языках проекта.

Тексты берутся из docs_text.py и language/*.json, поэтому отдельно переводить сайт не нужно.
Запуск: python tools/gen_site.py
"""
import json
import os
import re
import sys
import zipfile
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import hotkeys  # noqa: E402
import rules  # noqa: E402
from docs_text import LANGUAGES  # noqa: E402
from flags import flag_svg  # noqa: E402
from gen_docs import EXAMPLE, QUERY, RULES, TOKENS, write  # noqa: E402
from ui_version import VERSION  # noqa: E402

REPO = "https://github.com/Arkomiko/Fruity-Organizer-DataBase"
PACK = "FODB-mods-pack.zip"
# Страницы вики: адрес файла и заголовок (ключ из docs_text.py или строка интерфейса).
WIKI = (("start", "quick"), ("layouts", "layouts"), ("filters", "filters"), ("rules", "advanced"), ("safety", "safety"),
        ("themes", "themes"), ("settings", "Настройки"), ("hotkeys", "Горячие клавиши"), ("mods", "Моды"), ("build", "build"))
# Логотип из тех же букв, что в программе: 4 столбца на 7 строк.
LETTERS = {"F": ("####", "#...", "#...", "###.", "#...", "#...", "#..."), "O": (".##.", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."),
           "D": ("###.", "#..#", "#..#", "#..#", "#..#", "#..#", "###."), "B": ("###.", "#..#", "#..#", "###.", "#..#", "#..#", "###.")}
MOD_EXAMPLE = """# mods/My mod/index.json
{"name": "My mod", "type": "optimization", "version": "1.0", "author": "Me", "entry": "mod.py",
 "description": {"EN-en": "What it does"}}

# mods/My mod/mod.py
def activate(api):
    api.add_purpose_hook(lambda plugin: ["reverb"] if "hall" in plugin.name.casefold() else None)"""
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


def mod_folders() -> list[tuple[str, dict]]:
    """Папки модов проекта и их index.json."""
    root = os.path.join(ROOT, "mods")
    result = []
    for name in sorted(os.listdir(root), key=str.casefold):
        path = os.path.join(root, name, "index.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                result.append((name, json.load(f)))
    return result


def zip_name(mod_name: str) -> str:
    """Имя архива для адреса: без пробелов и скобок."""
    return re.sub(r"[^a-z0-9]+", "-", mod_name.casefold()).strip("-") + ".zip"


def add_mod(archive: zipfile.ZipFile, name: str) -> None:
    """Кладёт папку мода в архив. Дата постоянная: иначе архив менялся бы при каждой сборке сайта."""
    folder = os.path.join(ROOT, "mods", name)
    for base, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for file_name in sorted(files):
            path = os.path.join(base, file_name)
            inside = os.path.join(name, os.path.relpath(path, folder)).replace(os.sep, "/")
            entry = zipfile.ZipInfo(inside, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            with open(path, "rb") as f:
                archive.writestr(entry, f.read())


def write_mod_archives(out: str) -> None:
    """Архив каждого мода и общий пак: их можно скачать с сайта."""
    folder = os.path.join(out, "mods")
    os.makedirs(folder, exist_ok=True)
    mods = mod_folders()
    for name, _info in mods:
        with zipfile.ZipFile(os.path.join(folder, zip_name(name)), "w") as archive:
            add_mod(archive, name)
    with zipfile.ZipFile(os.path.join(folder, PACK), "w") as archive:
        for name, _info in mods:
            add_mod(archive, name)


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
        if slug == "section-mods":
            return folder + "mods.html"
        return folder + ("wiki/index.html" if slug == "wiki" else f"wiki/{slug}.html")

    def shell(self, prefix: str, slug: str | None, heading: str, body: str) -> str:
        """Общая оболочка: шапка, выбор языка и подвал."""
        lang = self.lang
        direction = ' dir="rtl"' if lang.get("rtl") else ""
        language_script = self.language_script() if prefix == "" else ""
        choices = "".join(f'<li><a href="{self.link(prefix, slug, code)}" lang="{other["html"]}" data-code="{code}"><img class="flag" src="{prefix}flags/{code}.svg" alt="" width="18" height="18">{escape(other["name"])}</a></li>'
                          for code, other in LANGUAGES.items())
        return f'''<!doctype html>
<html lang="{lang["html"]}"{direction}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{heading} | FODB</title>
<meta name="description" content="{self.text("intro")}">
<!-- Тема, выбранная кнопкой, ставится до отрисовки, чтобы страница не мигала другим цветом -->
<script>try{{const t=localStorage.getItem("fodb-theme");if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
{language_script}<!-- Значок вкладки браузера -->
<link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">
<link rel="alternate icon" href="{prefix}favicon.ico">
<link rel="stylesheet" href="{prefix}site.css">
<!-- Отмечаем, что скрипты работают: только тогда блоки появляются плавно -->
<script>document.documentElement.classList.add("js")</script>
<script src="{prefix}site.js" defer></script>
</head>
<body>
<!-- Шапка: название, разделы и выбор языка -->
<header><div class="bar">
<a class="name" href="{self.link(prefix, None)}"><img src="{prefix}favicon.svg" alt="" width="24" height="24">FODB</a>
<nav class="links">
<a href="{self.link(prefix, None)}">{self.text("home")}</a>
<a href="{self.link(prefix, "section-mods")}">{self.tr("Моды")}</a>
<a href="{self.link(prefix, "wiki")}">{self.text("wiki")}</a>
<a href="{REPO}/releases/latest">{self.text("download")}</a>
<a href="{REPO}">{self.text("source")}</a>
</nav>
<button class="theme" type="button" title="{self.tr("Тема")}" aria-label="{self.tr("Тема")}">
<svg class="sun" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><circle cx="8" cy="8" r="3"/><path d="M8 1v1.500M8 13.500V15M1 8h1.500M13.500 8H15M3 3l1 1M12 12l1 1M3 13l1-1M12 4l1-1"/></svg>
<svg class="moon" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M13.500 10.500A6 6 0 0 1 5.500 2.500a6 6 0 1 0 8 8z"/></svg>
</button>
<details class="langs"><summary><img class="flag" src="{prefix}flags/{self.code}.svg" alt="" width="18" height="18"><span class="current">{escape(lang["name"])}</span></summary><ul>{choices}</ul></details>
</div></header>
<!-- Содержимое страницы -->
<main>
{body}
</main>
<!-- Подвал: авторы и правовая оговорка -->
<footer><p class="author">By <a href="https://arkomiko.net">Arkomiko</a></p><p>{self.text("credits_t")}</p><p>{self.text("disclaimer")}</p></footer>
</body>
</html>
'''

    @staticmethod
    def language_script() -> str:
        """Только для главного адреса сайта: ведёт на сохранённый язык или на язык браузера. Прямые ссылки не трогает."""
        codes = {other["html"].lower(): code for code, other in LANGUAGES.items()}
        return f'''<!-- Выбор языка: сначала сохранённый, затем первый подходящий из настроек браузера -->
<script>(function(){{
const codes={json.dumps(codes)};
let saved=null;try{{saved=localStorage.getItem("fodb-language")}}catch(e){{}}
let code=saved;
if(!code){{for(const wanted of navigator.languages||[navigator.language||""]){{
const name=wanted.toLowerCase(),base=name.split("-")[0];
code=codes[name]||codes[Object.keys(codes).find(k=>k.split("-")[0]===base)];
if(code)break;
}}}}
if(code)location.replace(code+"/index.html");
}})()</script>
'''

    def home(self, prefix: str) -> str:
        """Главная страница."""
        lang = self.lang
        demo = "demo-ru.gif" if self.code in ("RU-ru", "UK-ua", "BE-by", "KK-kz") else "demo-en.gif"
        features = "".join(f"<li>{self.text(f'f{i}')}</li>" for i in range(1, 9))
        steps = "".join(f"<li>{self.text(f'q{i}')}</li>" for i in range(1, 4))
        news = "".join(f"<li>{self.text(f'n{i}')}</li>" for i in range(1, 6))
        pages = "".join(f'<li><a href="{self.link(prefix, slug)}">{self.title(key)}</a></li>' for slug, key in WIKI)
        body = f'''<!-- Первый экран: лозунг, кнопка и живой логотип -->
<section class="hero">
<div>
<h1>{escape(lang["taglines"][0])}</h1>
<p class="lead">{self.text("intro")}</p>
<a class="download" href="{REPO}/releases/latest">{self.text("download")}</a>
<p class="by">By <a href="https://arkomiko.net">Arkomiko</a></p>
</div>
{self.pads()}
</section>
<img class="shot reveal" src="{prefix}{demo}" alt="FODB">
<!-- Что появилось в последних версиях -->
<section class="reveal">
<h2>{self.text("news")}<span class="tag" dir="ltr">v{VERSION}</span></h2>
<ul class="cards">{news}</ul>
<p class="note"><a href="{self.link(prefix, "section-mods")}">{self.tr("Моды")}</a></p>
</section>
<!-- Возможности программы -->
<section class="reveal">
<h2>{self.text("features")}</h2>
<ul class="cards">{features}</ul>
</section>
<!-- Быстрый старт -->
<section class="reveal">
<h2>{self.text("quick")}</h2>
<ol>{steps}</ol>
</section>
<!-- Ссылки на страницы вики -->
<section class="reveal">
<h2>{self.text("wiki")}</h2>
<ul>{pages}</ul>
</section>'''
        return self.shell(prefix, None, "Fruity Organizer DataBase", body)

    @staticmethod
    def pads() -> str:
        """Логотип FODB из ячеек. Задержка растёт слева направо: по буквам бежит волна."""
        letters = []
        for index, letter in enumerate("FODB"):
            cells = ""
            for row in LETTERS[letter]:
                for column, value in enumerate(row):
                    cells += f'<i class="on" style="--d:{(index * 4 + column) * 0.06:.2f}s"></i>' if value == "#" else "<i></i>"
            letters.append(f'<div class="letter">{cells}</div>')
        return f'<div class="pads" role="img" aria-label="FODB">{"".join(letters)}</div>'

    def mod_section(self, prefix: str) -> str:
        """Раздел сайта «Моды»: описание, пак и карточка со скачиванием для каждого мода."""
        cards = ""
        for name, info in mod_folders():
            about = info["description"].get(self.code) or info["description"]["EN-en"]
            details = " / ".join(escape(str(info[key])) for key in ("type", "version", "author") if info.get(key))
            cards += (f'<div class="mod reveal"><h3 dir="ltr">{escape(info["name"])}</h3><small dir="ltr">{details}</small><p>{escape(about)}</p>'
                      f'<a class="download small" href="{prefix}mods/{zip_name(name)}" download>{self.text("mod_get")}</a></div>')
        body = f'''<!-- Заголовок раздела и общий пак -->
<section class="section-head">
<h1>{self.tr("Моды")}</h1>
<p class="lead">{self.text("f8")}</p>
<a class="download" href="{prefix}mods/{PACK}" download>{self.text("mod_pack")}</a>
<p class="note">{self.text("mod_install")}</p>
</section>
<!-- Каждый мод можно скачать отдельно -->
<div class="mods-grid">{cards}</div>
<!-- Как написать свой мод -->
<section class="reveal">
<h2>{self.tr("Модификации")}</h2>
<p>{self.text("mods_how")}</p>
<pre>{escape(MOD_EXAMPLE)}</pre>
</section>'''
        return self.shell(prefix, "section-mods", self.tr("Моды"), body)

    def mods_page(self) -> str:
        """Страница вики о модах: коротко и со ссылкой на раздел, где их можно скачать."""
        cards = ""
        for _name, info in mod_folders():
            about = info["description"].get(self.code) or info["description"]["EN-en"]
            cards += f'<div class="mod"><h3 dir="ltr">{escape(info["name"])}</h3><small dir="ltr">{escape(info["type"])}</small><p>{escape(about)}</p></div>'
        return (f'<p><a class="download small" href="{self.link("../../", "section-mods")}">{self.text("mod_pack")}</a></p>'
                + f'<p>{self.text("f8")}</p>{cards}<h2>{self.tr("Модификации")}</h2>'
                f'<p>{self.text("mods_how")}</p><pre>{escape(MOD_EXAMPLE)}</pre>')

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
        if slug == "mods":
            return self.mods_page()
        if slug == "hotkeys":
            rows = "".join(f'<tr><td>{tr(label)}</td><td dir="ltr">{default}</td></tr>' for _action, label, default in hotkeys.ACTIONS)
            return (f'<p>{tr("Дважды щёлкните строку, чтобы назначить другое сочетание.")}</p><p>{tr("Сочетания работают на любой раскладке: важна сама клавиша, а не её буква.")}</p>'
                    f'<table><tr><th>{tr("Действие")}</th><th>{tr("Клавиши")}</th></tr>{rows}</table>')
        return f"<p>{text('build_t')}</p><pre>./packaging/build.ps1</pre>"

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
        write(os.path.join(folder, "mods.html"), self.mod_section("../"))
        write(os.path.join(folder, "wiki", "index.html"), self.wiki_page("../../", "wiki", None))
        for slug, key in WIKI:
            write(os.path.join(folder, "wiki", slug + ".html"), self.wiki_page("../../", slug, key))


def main(out: str = os.path.join(ROOT, "GiDo")) -> int:
    """Создаёт сайт и возвращает число языков."""
    for name in ("site.css", "site.js"):  # оформление и скрипт лежат в tools/site, там их и правьте
        with open(os.path.join(ROOT, "tools", "site", name), encoding="utf-8") as f:
            write(os.path.join(out, name), f.read())
    write_mod_archives(out)
    for code in LANGUAGES:
        write(os.path.join(out, "flags", code + ".svg"), flag_svg(code))
    for code in LANGUAGES:
        Site(code, out).build()
    write(os.path.join(out, "index.html"), Site("EN-en", out).home(""))
    return len(LANGUAGES)


if __name__ == "__main__":
    print("languages:", main())
