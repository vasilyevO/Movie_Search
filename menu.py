"""
menu.py — user interaction via a console menu.

Responsible only for:
  • Inputting and validating user data.
  • Building a menu dictionary with associated actions.
  • Running the interactive menu loop.

Does not contain SQL, output formatting or database connection logic.
Called from main.py via run_menu().
"""

import sys

from formatter_UI import (
    Colors,
    MenuFormatter,
    MovieTableFormatter,
    GenreListFormatter,
    SearchHistoryFormatter,
    InfoMessage,
)
from sql_requests import MovieSearcher
from mongo_log_search import SearchLogger
from log_search import SearchStats
from logger import get_logger

log = get_logger(__name__)


# ── Input support functions ─────────────────────────────────────────────

def _prompt(message: str) -> str:
    """Displays a prompt and returns the entered string (strip)."""
    return input(message).strip()


def _prompt_int(message: str, min_val: int, max_val: int) -> int | None:
    """
    Requests an integer within the range [min_val, max_val].

    Returns:
        The entered number, or None if the input is invalid.
    """
    raw = _prompt(message)
    try:
        value = int(raw)
    except ValueError:
        log.warning("Некорректный ввод числа: %r", raw)
        print(InfoMessage("Ожидается целое число. Попробуйте снова.", "error"))
        return None

    if not (min_val <= value <= max_val):
        log.warning(
            "Число вне диапазона: %d (допустимо %d–%d)", value, min_val, max_val
        )
        print(InfoMessage(
            f"Значение должно быть от {min_val} до {max_val}.", "warning"
        ))
        return None

    return value


def _ask_next_page() -> bool:
    """It asks whether to display the next page of results."""
    answer = _prompt(
        f"\n{Colors.BOLD}Показать следующие результаты? [y/n]: {Colors.RESET}"
    ).lower()
    return answer in ("y", "yes", "д", "да")


# ── Secure logging in MongoDB ──────────────────────────────────────────

def _safe_log(
    logger: SearchLogger,
    search_type: str,
    params: dict,
    results_count: int,
) -> None:
    """Saves the query to MongoDB without interrupting operations in the event of a failure."""
    try:
        logger.log_search(search_type, params, results_count)
    except (ConnectionError, RuntimeError, ValueError) as exc:
        log.error("Не удалось записать запрос в MongoDB: %s", exc)
        print(InfoMessage(f"[Лог] Не удалось сохранить запрос: {exc}", "warning"))


# ── Действия меню ─────────────────────────────────────────────────────────────

def run_keyword_search(searcher: MovieSearcher, logger: SearchLogger) -> None:
    """Scenario 1: Searching for films by keyword in the title (page by page)."""
    keyword = _prompt(f"{Colors.BOLD}Введите ключевое слово: {Colors.RESET}")

    if not keyword:
        print(InfoMessage("Ключевое слово не может быть пустым.", "warning"))
        return

    try:
        total_count = searcher.count_by_keyword(keyword)
    except (ConnectionError, RuntimeError) as exc:
        log.error("Ошибка поиска по слову '%s': %s", keyword, exc)
        print(InfoMessage(str(exc), "error"))
        return

    if total_count == 0:
        print(InfoMessage(f"По запросу «{keyword}» ничего не найдено.", "warning"))
        _safe_log(logger, "keyword", {"keyword": keyword}, 0)
        return

    print(InfoMessage(f"Всего найдено: {total_count} фильм(ов).", "info"))

    shown = 0
    for page in searcher.search_by_keyword(keyword):
        print(f"\n{MovieTableFormatter(page, start_idx=shown + 1)}")
        shown += len(page)
        if len(page) < searcher.page_size or shown >= total_count:
            print(InfoMessage("Это все найденные результаты.", "success"))
            break
        if not _ask_next_page():
            break

    _safe_log(logger, "keyword", {"keyword": keyword}, total_count)


def run_genre_year_search(searcher: MovieSearcher, logger: SearchLogger) -> None:
    """Scenario 2: Search by genre and year range."""
    try:
        genres = searcher.get_genres()
        min_year, max_year = searcher.get_year_range()
    except (ConnectionError, RuntimeError) as exc:
        log.error("Ошибка получения метаданных: %s", exc)
        print(InfoMessage(str(exc), "error"))
        return

    if not genres:
        print(InfoMessage("Жанры не найдены в базе данных.", "warning"))
        return

    print(GenreListFormatter(genres))
    print(
        f"\n{Colors.HEADER}Диапазон лет в базе: "
        f"{Colors.SUCCESS}{min_year} — {max_year}{Colors.RESET}"
    )

    # User selects a genre by its number from the displayed list
    genre_num = _prompt_int(
        f"\n{Colors.BOLD}Введите номер жанра (1–{len(genres)}): {Colors.RESET}",
        1, len(genres),
    )
    if genre_num is None:
        return
    genre = genres[genre_num - 1]   # number → genre name (list is 0-indexed)

    year_from = _prompt_int(
        f"{Colors.BOLD}Год ОТ ({min_year}–{max_year}): {Colors.RESET}",
        min_year, max_year,
    )
    if year_from is None:
        return

    year_to = _prompt_int(
        f"{Colors.BOLD}Год ДО ({year_from}–{max_year}): {Colors.RESET}",
        year_from, max_year,
    )
    if year_to is None:
        return

    try:
        total_count = searcher.count_by_genre_year(genre, year_from, year_to)
    except (ConnectionError, RuntimeError) as exc:
        log.error("Ошибка поиска по жанру '%s': %s", genre, exc)
        print(InfoMessage(str(exc), "error"))
        return

    if total_count == 0:
        print(InfoMessage(
            f"По жанру «{genre}» за {year_from}–{year_to} ничего не найдено.",
            "warning",
        ))
        _safe_log(
            logger, "genre_year",
            {"genre": genre, "year_from": year_from, "year_to": year_to}, 0,
        )
        return

    print(InfoMessage(f"Всего найдено: {total_count} фильм(ов).", "info"))

    shown = 0
    for page in searcher.search_by_genre_year(genre, year_from, year_to):
        print(f"\n{MovieTableFormatter(page, start_idx=shown + 1)}")
        shown += len(page)
        if len(page) < searcher.page_size or shown >= total_count:
            print(InfoMessage("Это все найденные результаты.", "success"))
            break
        if not _ask_next_page():
            break

    _safe_log(
        logger, "genre_year",
        {"genre": genre, "year_from": year_from, "year_to": year_to},
        total_count,
    )


def show_popular_searches(stats: SearchStats) -> None:
    """Displays the top 5 most frequent search queries."""
    try:
        records = stats.get_popular_searches(limit=5)
        print(SearchHistoryFormatter(records, "ТОП-5 ПОПУЛЯРНЫХ ЗАПРОСОВ"))
    except (ConnectionError, RuntimeError) as exc:
        log.error("Ошибка получения популярных запросов: %s", exc)
        print(InfoMessage(str(exc), "error"))


def show_recent_searches(stats: SearchStats) -> None:
    """Displays the last 5 unique search queries."""
    try:
        records = stats.get_recent_unique_searches(limit=5)
        print(SearchHistoryFormatter(records, "5 ПОСЛЕДНИХ УНИКАЛЬНЫХ ЗАПРОСОВ"))
    except (ConnectionError, RuntimeError) as exc:
        log.error("Ошибка получения последних запросов: %s", exc)
        print(InfoMessage(str(exc), "error"))


def exit_app(logger: SearchLogger, stats: SearchStats) -> None:
    """Correctly closes the application."""
    print(InfoMessage("\n  До свидания! 🎬\n", "success"))
    log.info("Приложение завершено пользователем")
    logger.close()
    stats.close()
    sys.exit(0)


# ── Menu glossary ──────────────────────────────────────────────────────────────

def _build_menu_actions(
    searcher: MovieSearcher,
    logger: SearchLogger,
    stats: SearchStats,
) -> dict:
    """
    Creates a dictionary of menu items with associated actions.

    Structure: {"key": ("Item name", callable)}

    To add a new item, simply add a line here.
    There is no need to modify either MenuFormatter or run_menu().
    """
    return {
        "1": ("Поиск по ключевому слову",
              lambda: run_keyword_search(searcher, logger)),
        "2": ("Поиск по жанру и диапазону годов",
              lambda: run_genre_year_search(searcher, logger)),
        "3": ("ТОП-5 популярных запросов",
              lambda: show_popular_searches(stats)),
        "4": ("5 последних уникальных запросов",
              lambda: show_recent_searches(stats)),
        "0": ("Выход",
              lambda: exit_app(logger, stats)),
    }


# ── Public menu entry point ──────────────────────────────────────────────

def run_menu(
    searcher: MovieSearcher,
    logger: SearchLogger,
    stats: SearchStats,
) -> None:
    """
    Starts an interactive menu loop.

    Called from main.py — the only public function in this module.

    Args:
        searcher: A MovieSearcher instance for search queries.
        logger: A SearchLogger instance for logging history.
    """
    menu_actions   = _build_menu_actions(searcher, logger, stats)
    menu_formatter = MenuFormatter(menu_actions)

    print(InfoMessage(
        "\n  Добро пожаловать в систему поиска фильмов Sakila! 🎬", "success"
    ))

    while True:
        print(menu_formatter)

        try:
            choice = _prompt(f"{Colors.BOLD}Ваш выбор: {Colors.RESET}")
        except (EOFError, KeyboardInterrupt):
            choice = "0"

        # .get() — одно обращение к словарю: и проверка и получение
        menu_item = menu_actions.get(choice)

        if menu_item is None:
            log.warning("Неверный пункт меню: %r", choice)
            print(InfoMessage(
                f"Неверный выбор. Доступны: {', '.join(menu_actions)}",
                "warning",
            ))
            continue

        _, action = menu_item
        action()
