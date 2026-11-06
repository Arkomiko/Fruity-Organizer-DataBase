# Roadmap

## Built-in plugin scanning

FODB currently reads the plugin database that FL Studio's Plugin Manager has already created. The goal is to make FODB work on its own: find plugins, verify them and create the database entries, with the filters and organizer FODB already has.

Planned:

- Scan VST, VST3 and CLAP folders chosen by the user
- Detect new, changed and removed plugins
- Create database entries that FL Studio can read
- Filter scan results before anything is written
- Back up the database before every change, as FODB does today

This will be an independent implementation, written from the database files themselves and public plugin format specifications. It will not use code from FL Studio or Plugin Manager.

---

# Планы

## Встроенный поиск плагинов

Сейчас FODB читает базу плагинов, которую уже создал Plugin Manager из FL Studio. Цель в том, чтобы FODB работал сам: находил плагины, проверял их и создавал записи в базе, сохраняя свои фильтры и органайзер.

Что планируется:

- Поиск в папках VST, VST3 и CLAP, которые выберет пользователь
- Определение новых, изменённых и удалённых плагинов
- Создание записей базы, которые читает FL Studio
- Фильтрация результатов поиска до записи в базу
- Бэкап базы перед каждым изменением, как сейчас

Это будет независимая реализация по самим файлам базы и открытым описаниям форматов плагинов. Код FL Studio и Plugin Manager использоваться не будет.
