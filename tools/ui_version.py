"""Номер версии программы для сайта. Берётся из src/ui.py, чтобы не хранить его в двух местах."""
import os
import re

_UI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "ui.py")
with open(_UI, encoding="utf-8") as _f:
    VERSION = re.search(r'^VERSION = "([^"]+)"', _f.read(), re.M).group(1)
