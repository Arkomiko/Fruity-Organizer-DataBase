"""Other Integration BD: данные о плагинах из открытого каталога, поиск по имени."""
import json
import os
import threading

URL = "https://raw.githubusercontent.com/Arkomiko/Fruity-Organizer-DataBase/main/mods/Other%20Integration%20BD%20%28experimentally%29/catalog.json"
BUTTON = {"EN-en": "Update catalog", "RU-ru": "Обновить каталог"}
DONE = {"EN-en": "Catalog updated: {count} plugins.", "RU-ru": "Каталог обновлён: плагинов {count}."}
FAILED = {"EN-en": "Could not download the catalog.", "RU-ru": "Не удалось скачать каталог."}


def activate(api):
    """Подключает каталог: скачанная копия важнее той, что идёт с модом."""
    catalog = {}

    def load():
        catalog.clear()
        catalog.update(api.read_json("catalog.json", {}))
        catalog.update(api.load_data({}))
        return sorted(catalog, key=len, reverse=True)

    ordered = [load()]

    def find(plugin):
        name = plugin.name.casefold()
        for known in ordered[0]:
            if name.startswith(known) and (len(name) == len(known) or not name[len(known)].isalpha()):
                return catalog[known]
        return None

    def vendor(plugin):
        entry = find(plugin)
        return entry.get("vendor") if entry else None

    def purpose(plugin):
        entry = find(plugin)
        return [entry["purpose"]] if entry and entry.get("purpose") else None

    def search(plugin):
        entry = find(plugin)
        return " ".join(entry.get("tags", ())) if entry else None

    def update():
        """Скачивает каталог в фоне, а окно только ждёт результат."""
        import ui
        app = api.app
        temp = api.data_path() + ".download"
        box = {}

        def work():
            try:
                if api.download(URL, temp):
                    with open(temp, encoding="utf-8") as f:
                        box["data"] = dict(json.load(f))
            except (OSError, ValueError, TypeError):
                pass
            box["done"] = True

        def wait():
            if "done" not in box:
                app.root.after(100, wait)
                return
            if os.path.exists(temp):
                os.remove(temp)
            if "data" in box:
                api.save_data(box["data"])
                ordered[0] = load()
                app.refresh()
                app.show_message(api.text(DONE).format(count=len(catalog)))
            else:
                app.show_error(api.text(FAILED))

        threading.Thread(target=work, daemon=True).start()
        wait()

    api.add_vendor_hook(vendor)
    api.add_purpose_hook(purpose, priority=70)
    api.add_search_hook(search)
    api.add_action(BUTTON, update)
