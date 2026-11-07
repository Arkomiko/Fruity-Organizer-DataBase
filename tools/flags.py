"""Маленькие флаги для выбора языка: упрощённые рисунки SVG. Рисуются в размере 30 на 20, показывается квадрат 20 на 20.

Значки-эмодзи не подходят: Chrome на Windows показывает вместо флага две буквы.
"""
import math


def _rows(*colors) -> str:
    """Горизонтальные полосы одинаковой высоты."""
    height = 20 / len(colors)
    return "".join(f'<rect y="{i * height:.2f}" width="30" height="{height + 0.1:.2f}" fill="{c}"/>' for i, c in enumerate(colors))


def _columns(*colors) -> str:
    """Вертикальные полосы одинаковой ширины."""
    width = 30 / len(colors)
    return "".join(f'<rect x="{i * width:.2f}" width="{width + 0.1:.2f}" height="20" fill="{c}"/>' for i, c in enumerate(colors))


def _back(color: str) -> str:
    """Сплошной фон."""
    return f'<rect width="30" height="20" fill="{color}"/>'


def _star(x: float, y: float, r: float, color: str) -> str:
    """Пятиконечная звезда."""
    points = []
    for i in range(10):
        radius = r if i % 2 == 0 else r * 0.4
        angle = -math.pi / 2 + i * math.pi / 5
        points.append(f"{x + radius * math.cos(angle):.2f},{y + radius * math.sin(angle):.2f}")
    return f'<polygon points="{" ".join(points)}" fill="{color}"/>'


def _crescent(x: float, y: float, r: float, ink: str, back: str) -> str:
    """Полумесяц: круг, частично закрытый кругом цвета фона."""
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{ink}"/><circle cx="{x + r * 0.28:.2f}" cy="{y}" r="{r * 0.8:.2f}" fill="{back}"/>'


def _slices(*colors) -> str:
    """Секторы от центра, как нарезанная пицца: сверху и по часовой стрелке."""
    x, y, radius = 15, 10, 20
    step = 2 * math.pi / len(colors)
    parts = []
    for index, color in enumerate(colors):
        start, end = -math.pi / 2 + index * step, -math.pi / 2 + (index + 1) * step + 0.01
        parts.append(f'<polygon points="{x},{y} {x + radius * math.cos(start):.2f},{y + radius * math.sin(start):.2f} '
                     f'{x + radius * math.cos(end):.2f},{y + radius * math.sin(end):.2f}" fill="{color}"/>')
    return "".join(parts)


FLAGS = {
    "EN-en": _back("#012169") + '<path d="M0 0 30 20M30 0 0 20" stroke="#fff" stroke-width="4"/><path d="M0 0 30 20M30 0 0 20" stroke="#C8102E" stroke-width="1.6"/>'
             '<path d="M15 0v20M0 10h30" stroke="#fff" stroke-width="6"/><path d="M15 0v20M0 10h30" stroke="#C8102E" stroke-width="3.5"/>',
    "RU-ru": _rows("#FFFFFF", "#0039A6", "#D52B1E"),
    "ZH-cn": _back("#DE2910") + _star(7, 7, 4.5, "#FFDE00") + _star(13.5, 3, 1.3, "#FFDE00") + _star(15.5, 6, 1.3, "#FFDE00") + _star(15.5, 9.5, 1.3, "#FFDE00") + _star(13.5, 12, 1.3, "#FFDE00"),
    "ES-es": _rows("#AA151B", "#F1BF00", "#F1BF00", "#AA151B"),
    "HI-in": _rows("#FF9933", "#FFFFFF", "#138808") + '<circle cx="15" cy="10" r="2.6" fill="none" stroke="#000080" stroke-width="0.9"/>',
    "FR-fr": _columns("#0055A4", "#FFFFFF", "#EF4135"),
    "BN-bd": _back("#006A4E") + '<circle cx="13.5" cy="10" r="6" fill="#F42A41"/>',
    "PT-br": _back("#009C3B") + '<polygon points="15,2.500 27,10 15,17.500 3,10" fill="#FFDF00"/><circle cx="15" cy="10" r="4.200" fill="#002776"/>',
    "UR-pk": _back("#01411C") + '<rect width="7.500" height="20" fill="#FFFFFF"/>' + _crescent(18, 10, 5, "#FFFFFF", "#01411C") + _star(22, 6.8, 1.8, "#FFFFFF"),
    "ID-id": _rows("#FF0000", "#FFFFFF"),
    "DE-de": _rows("#000000", "#DD0000", "#FFCE00"),
    "JA-jp": _back("#FFFFFF") + '<circle cx="15" cy="10" r="6" fill="#BC002D"/>',
    "TR-tr": _back("#E30A17") + _crescent(12, 10, 5.5, "#FFFFFF", "#E30A17") + _star(19.5, 10, 2.6, "#FFFFFF"),
    "KO-kr": _back("#FFFFFF") + '<path d="M9.800 10a5.200 5.200 0 0 1 10.400 0z" fill="#CD2E3A"/><path d="M9.800 10a5.200 5.200 0 0 0 10.400 0z" fill="#0047A0"/>'
             '<path d="M3 4.500 6 2.500M24 2.500 27 4.500M3 15.500 6 17.500M24 17.500 27 15.500" stroke="#000" stroke-width="1.400"/>',
    "VI-vn": _back("#DA251D") + _star(15, 10, 6, "#FFFF00"),
    "IT-it": _columns("#009246", "#FFFFFF", "#CE2B37"),
    "PL-pl": _rows("#FFFFFF", "#DC143C"),
    "UK-ua": _rows("#0057B7", "#FFD700"),
    "TH-th": _rows("#A51931", "#F4F5F8", "#2D2A4A", "#2D2A4A", "#F4F5F8", "#A51931"),
    "KK-kz": _back("#00AFCA") + '<circle cx="15" cy="9" r="4" fill="#FEC50C"/>',
    "UZ-uz": _rows("#0099B5", "#FFFFFF", "#1EB53A") + _crescent(6, 3.4, 2.2, "#FFFFFF", "#0099B5"),
    "BE-by": '<rect width="30" height="13.400" fill="#C8313E"/><rect y="13.300" width="30" height="6.700" fill="#4AA657"/>',
    "AZ-az": _rows("#00B5E2", "#EF3340", "#509E2F") + _crescent(14, 10, 2.5, "#FFFFFF", "#EF3340") + _star(17.5, 10, 1.4, "#FFFFFF"),
    "HY-am": _rows("#D90012", "#0033A0", "#F2A800"),
    "ISV-sl": _slices("#FFFFFF", "#0C4DA2", "#D52B1E", "#1E9E48", "#35B8E8", "#FFD500", "#F58A1F"),
    "HE-il": _back("#FFFFFF") + '<rect y="2.500" width="30" height="3" fill="#0038B8"/><rect y="14.500" width="30" height="3" fill="#0038B8"/>'
             '<path d="M15 6.200 18.300 11.900H11.700zM15 13.800 11.700 8.100H18.300z" fill="none" stroke="#0038B8" stroke-width="0.900"/>',
}


# У этих флагов главное у древка, поэтому квадрат берётся с левого края, а не из середины.
LEFT_ALIGNED = {"ZH-cn", "UZ-uz"}


def flag_svg(code: str) -> str:
    """Флаг в квадрате со скруглёнными углами, в той же пропорции, что ячейки логотипа FODB."""
    x = 0 if code in LEFT_ALIGNED else 5
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} 0 20 20" width="20" height="20">'
            f'<clipPath id="r"><rect x="{x}" width="20" height="20" rx="3.800"/></clipPath>'
            f'<g clip-path="url(#r)">{FLAGS[code]}</g>'
            f'<rect x="{x + 0.3}" y="0.300" width="19.400" height="19.400" rx="3.500" fill="none" stroke="#000" stroke-opacity=".22" stroke-width=".6"/></svg>\n')
