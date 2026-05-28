"""
menu.py — консольное меню демо-версии.

Три пункта: поиск по ключевому слову, последние запросы, выход.
Простой текстовый вывод без цветов и форматтеров.
"""

import sys
from sql_requests import MovieSearcher
from log_search_hist import SearchLogger
from log_search import SearchStats


# ── Функции ввода ─────────────────────────────────────────────────────────────

def _prompt(message: str) -> str:
    """Выводит подсказку и возвращает введённую строку (strip)."""
    return input(message).strip()


def _ask_next_page() -> bool:
    """Спрашивает, показывать ли следующую страницу."""
    return _prompt("\nПоказать следующие 10 результатов? [y/n]: ").lower() \
           in ("y", "yes", "д", "да")


# ── Вывод фильмов ─────────────────────────────────────────────────────────────

def _print_movies(page: list[dict], start_idx: int) -> None:
    """Выводит страницу фильмов простым текстом."""
    print()
    for i, row in enumerate(page, start=start_idx):
        title    = row.get("title",        "N/A")
        category = row.get("category",     "N/A")
        year     = row.get("release_year", "N/A")
        rating   = row.get("rating",       "N/A")
        print(f"  {i}. {title} | {category} | {year} | {rating}")


# ── Запись в MongoDB ──────────────────────────────────────────────────────────

def _safe_log(
    logger: SearchLogger,
    search_type: str,
    params: dict,
    results_count: int,
) -> None:
    """Записывает запрос в MongoDB. При сбое выводит предупреждение."""
    try:
        logger.log_search(search_type, params, results_count)
        print(f"  [MongoDB] Запрос сохранён ({results_count} результатов)")
    except (ConnectionError, RuntimeError) as exc:
        print(f"  [MongoDB] Не удалось сохранить запрос: {exc}")


# ── Действия меню ─────────────────────────────────────────────────────────────

def run_keyword_search(searcher: MovieSearcher, logger: SearchLogger) -> None:
    """Поиск фильмов по ключевому слову с постраничным выводом."""
    keyword = _prompt("\nВведите ключевое слово: ")

    if not keyword:
        print("Ключевое слово не может быть пустым.")
        return

    try:
        total_count = searcher.count_by_keyword(keyword)
    except (ConnectionError, RuntimeError) as exc:
        print(f"Ошибка подключения к MySQL: {exc}")
        return

    if total_count == 0:
        print(f"По запросу «{keyword}» ничего не найдено.")
        _safe_log(logger, "keyword", {"keyword": keyword}, 0)
        return

    print(f"\nНайдено фильмов: {total_count}")
    print("-" * 60)

    shown = 0
    for page in searcher.search_by_keyword(keyword):
        _print_movies(page, start_idx=shown + 1)
        shown += len(page)

        if len(page) < searcher.page_size or shown >= total_count:
            print("\nЭто все найденные результаты.")
            break
        if not _ask_next_page():
            break

    _safe_log(logger, "keyword", {"keyword": keyword}, total_count)


def show_recent_searches(stats: SearchStats) -> None:
    """Выводит 5 последних уникальных поисковых запросов из MongoDB."""
    try:
        records = stats.get_recent_unique_searches(limit=5)
    except (ConnectionError, RuntimeError) as exc:
        print(f"Ошибка подключения к MongoDB: {exc}")
        return

    print("\n" + "=" * 60)
    print("  5 ПОСЛЕДНИХ УНИКАЛЬНЫХ ЗАПРОСОВ")
    print("=" * 60)

    if not records:
        print("  История запросов пуста.")
        return

    for i, rec in enumerate(records, start=1):
        s_type = rec.get("search_type", "N/A")
        params = ", ".join(
            f"{k}: {v}" for k, v in rec.get("params", {}).items()
        )
        count  = rec.get("results_count", 0)
        ts     = rec.get("timestamp", "N/A")
        print(f"  {i}. [{s_type}] {params}")
        print(f"     результатов: {count}  |  {ts}")


def exit_app(logger: SearchLogger, stats: SearchStats) -> None:
    """Завершает работу приложения."""
    print("\nДо свидания!\n")
    logger.close()
    stats.close()
    sys.exit(0)


# ── Словарь меню ──────────────────────────────────────────────────────────────

def build_menu_actions(
    searcher: MovieSearcher,
    logger: SearchLogger,
    stats: SearchStats,
) -> dict:
    """
    Словарь пунктов меню с привязанными действиями.
    Добавить новый пункт — одна строка здесь, цикл не трогаем.
    """
    return {
        "1": ("Поиск по ключевому слову",
              lambda: run_keyword_search(searcher, logger)),
        "2": ("5 последних уникальных запросов",
              lambda: show_recent_searches(stats)),
        "0": ("Выход",
              lambda: exit_app(logger, stats)),
    }


# ── Цикл меню ─────────────────────────────────────────────────────────────────

def run_menu(
    searcher: MovieSearcher,
    logger: SearchLogger,
    stats: SearchStats,
) -> None:
    """
    Запускает интерактивный цикл меню.
    Получает готовые компоненты из main.py.
    Цикл не знает про конкретные действия — вызывает callable из словаря.
    """
    menu_actions = build_menu_actions(searcher, logger, stats)

    print("\nДобро пожаловать в систему поиска фильмов Sakila!")

    while True:
        print("\n" + "=" * 40)
        for key, (label, _) in menu_actions.items():
            print(f"  [{key}]  {label}")
        print("=" * 40)

        try:
            choice = _prompt("Ваш выбор: ")
        except (EOFError, KeyboardInterrupt):
            choice = "0"

        # .get() — одно обращение к словарю: и проверка и получение
        menu_item = menu_actions.get(choice)

        if menu_item is None:
            print(f"Неверный выбор. Доступны: {', '.join(menu_actions)}")
            continue

        _, action = menu_item
        action()
