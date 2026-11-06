# Рецепт PyInstaller для портативного exe из одного файла. Запускается через build.ps1.
import os

ROOT = os.path.abspath(SPECPATH)

# Модули Python, которые программа не использует: без них файл меньше, а запуск быстрее.
EXCLUDES = [
    "asyncio", "bz2", "concurrent", "curses", "decimal", "difflib", "distutils", "doctest", "email", "ftplib",
    "html", "http", "lzma", "multiprocessing", "pdb", "pydoc", "sqlite3", "ssl", "statistics", "test", "tkinter.test",
    "unittest", "urllib", "xml", "xmlrpc", "PIL",
]
# Ненужные данные Tcl/Tk: часовые пояса, каталоги сообщений, примеры, старые кодировки.
DROP_PARTS = ("tzdata", "/msgs/", "\\msgs\\", "/demos/", "\\demos\\", "/images/", "\\images\\", "/http1", "\\http1",
              "/opt0", "\\opt0", "/tcl8/", "\\tcl8\\", "/dde", "\\dde", "/reg1", "\\reg1", "/nls/", "\\nls\\")
KEEP_ENCODINGS = ("ascii.enc", "utf-8.enc", "cp1251.enc", "cp1252.enc", "iso8859-1.enc")


def keep_data(name: str) -> bool:
    lowered = name.lower()
    if any(part in lowered for part in DROP_PARTS):
        return False
    if "encoding" in lowered and lowered.endswith(".enc"):
        return lowered.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] in KEEP_ENCODINGS
    return True


a = Analysis(
    [os.path.join(ROOT, "src", "main.py")],
    pathex=[os.path.join(ROOT, "src")],
    datas=[(os.path.join(ROOT, "assets", "app.ico"), "assets"), (os.path.join(ROOT, "language"), "language")],
    excludes=EXCLUDES,
    optimize=2,
)
a.datas = [entry for entry in a.datas if keep_data(entry[0])]

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name="FODB",
    icon=os.path.join(ROOT, "assets", "app.ico"),
    console=False,
    strip=False,
    upx=False,
    version=os.path.join(ROOT, "assets", "version_info.txt"),
)
