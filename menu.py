"""
menu.py — взаимодействие с пользователем через консольное меню.

Отвечает только за:
  • Ввод и валидацию данных от пользователя.
  • Построение словаря меню с привязанными действиями.
  • Запуск интерактивного цикла меню.

Не содержит SQL, форматирования вывода и логики подключения к БД.
Вызывается из main.py через run_menu().
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


# ── Вспомогательные функции ввода ─────────────────────────────────────────────

def _prompt(message: str) -> str:
    """Выводит подсказку и возвращает введённую строку (strip)."""
    return input(message).strip()


def _prompt_int(message: str, min_val: int, max_val: int) -> int | None:
    """
    Запрашивает целое число в диапазоне [min_val, max_val].

    Returns:
        Введённое число или None при некорректном вводе.
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
    """Спрашивает, показывать ли следующую страницу результатов."""
    answer = _prompt(
        f"\n{Colors.BOLD}Показать следующие результаты? [y/n]: {Colors.RESET}"
    ).lower()
    return answer in ("y", "yes", "д", "да")


# ── Безопасное логирование в MongoDB ──────────────────────────────────────────

def _safe_log(
    logger: SearchLogger,
    search_type: str,
    params: dict,
    results_count: int,
) -> None:
    """Сохраняет запрос в MongoDB, не прерывая работу при сбое."""
    try:
        logger.log_search(search_type, params, results_count)
    except (ConnectionError, RuntimeError, ValueError) as exc:
        log.error("Не удалось записать запрос в MongoDB: %s", exc)
        print(InfoMessage(f"[Лог] Не удалось сохранить запрос: {exc}", "warning"))


# ── Действия меню ─────────────────────────────────────────────────────────────

def run_keyword_search(searcher: MovieSearcher, logger: SearchLogger) -> None:
    """Сценарий 1: поиск фильмов по ключевому слову в названии (постранично)."""
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
    """Сценарий 2: поиск по жанру + диапазону годов."""
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
    """Отображает ТОП-5 самых частых поисковых запросов."""
    try:
        records = stats.get_popular_searches(limit=5)
        print(SearchHistoryFormatter(records, "ТОП-5 ПОПУЛЯРНЫХ ЗАПРОСОВ"))
    except (ConnectionError, RuntimeError) as exc:
        log.error("Ошибка получения популярных запросов: %s", exc)
        print(InfoMessage(str(exc), "error"))


def show_recent_searches(stats: SearchStats) -> None:
    """Отображает 5 последних уникальных поисковых запросов."""
    try:
        records = stats.get_recent_unique_searches(limit=5)
        print(SearchHistoryFormatter(records, "5 ПОСЛЕДНИХ УНИКАЛЬНЫХ ЗАПРОСОВ"))
    except (ConnectionError, RuntimeError) as exc:
        log.error("Ошибка получения последних запросов: %s", exc)
        print(InfoMessage(str(exc), "error"))


def exit_app(logger: SearchLogger, stats: SearchStats) -> None:
    """Корректно завершает работу приложения."""
    print(InfoMessage("\n  До свидания! 🎬\n", "success"))
    log.info("Приложение завершено пользователем")
    logger.close()
    stats.close()
    sys.exit(0)


# ── Словарь меню ──────────────────────────────────────────────────────────────

def _build_menu_actions(
    searcher: MovieSearcher,
    logger: SearchLogger,
    stats: SearchStats,
) -> dict:
    """
    Строит словарь пунктов меню с привязанными действиями.

    Структура: {"ключ": ("Название пункта", callable)}

    Чтобы добавить новый пункт — достаточно добавить одну строку сюда.
    Ни MenuFormatter, ни run_menu() трогать не нужно.
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


# ── Публичная точка входа в меню ──────────────────────────────────────────────

def run_menu(
    searcher: MovieSearcher,
    logger: SearchLogger,
    stats: SearchStats,
) -> None:
    """
    Запускает интерактивный цикл меню.

    Вызывается из main.py — единственная публичная функция этого модуля.

    Args:
        searcher: Экземпляр MovieSearcher для поисковых запросов.
        logger:   Экземпляр SearchLogger для записи истории.
        stats:    Экземпляр SearchStats для чтения статистики.
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
