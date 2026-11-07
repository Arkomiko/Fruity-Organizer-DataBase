"""Status Indicators: цветная полоска у строк списка показывает состояние плагина."""
import time

ORGANIZED, FAVORITE, NEW = "#5FC46E", "#FFB23E", "#4A9BF0"
RECENT_SECONDS = 14 * 24 * 3600


def activate(api):
    """Подключает полоску."""
    def marker(plugin):
        folder = (plugin.organized_in or "").casefold()
        if "favorit" in folder or "favourit" in folder or "избран" in folder:
            return FAVORITE
        if folder:
            return ORGANIZED
        if plugin.group == "New" or (plugin.installed and time.time() - plugin.installed < RECENT_SECONDS):
            return NEW
        return None

    api.set_row_marker(marker)
