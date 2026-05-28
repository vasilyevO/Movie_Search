"""
sql_requests.py — SQL-запросы и методы поиска фильмов в базе Sakila.

Получает конфиг подключения из main.py через __init__ и передаёт
его в DBConnection. Не знает про pymysql и глобальные переменные.
Вызывается из main.py.
"""

from typing import Generator

from db_connection import DBConnection
from logger import get_logger

log = get_logger(__name__)


class MovieSearcher(DBConnection):
    """
    Выполняет поиск фильмов в базе данных Sakila.

    Наследует DBConnection — получает _fetch_all, _fetch_one, _paginate.
    Все SQL-запросы параметризованы через %s (защита от инъекций).
    Постраничный обход реализован через генераторы (экономия памяти).

    Args:
        config: Словарь параметров pymysql.connect() из main.py.
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    # ── Метаданные ────────────────────────────────────────────────────────────

    def get_genres(self) -> list[str]:
        """Возвращает отсортированный список жанров из таблицы category."""
        query = "SELECT name FROM category ORDER BY name"
        rows = self._fetch_all(query)
        return [row['name'] for row in rows]

    def get_year_range(self) -> tuple[int, int]:
        """Возвращает (min_year, max_year) из таблицы film."""
        query = (
            "SELECT MIN(release_year) AS mn, MAX(release_year) AS mx "
            "FROM film"
        )
        row = self._fetch_one(query)
        if row and row['mn'] is not None:
            return int(row['mn']), int(row['mx'])
        return 0, 0

    # ── Подсчёт результатов ───────────────────────────────────────────────────

    def count_by_keyword(self, keyword: str) -> int:
        """Возвращает количество фильмов, подходящих под ключевое слово."""
        query = "SELECT COUNT(*) AS cnt FROM film WHERE title LIKE %s"
        row = self._fetch_one(query, (f'%{keyword.strip()}%',))
        return int(row['cnt']) if row else 0

    def count_by_genre_year(
        self, genre: str, year_from: int, year_to: int
    ) -> int:
        """Возвращает количество фильмов по жанру и диапазону лет."""
        query = """
            SELECT COUNT(*) AS cnt
            FROM film f
            JOIN film_category fc ON f.film_id      = fc.film_id
            JOIN category      c  ON fc.category_id = c.category_id
            WHERE c.name = %s
              AND f.release_year BETWEEN %s AND %s
        """
        row = self._fetch_one(query, (genre.strip(), year_from, year_to))
        return int(row['cnt']) if row else 0

    # ── Поиск по ключевому слову ──────────────────────────────────────────────

    def search_by_keyword(
        self, keyword: str
    ) -> Generator[list[dict], None, None]:
        """
        Генератор постраничного поиска фильмов по части названия.

        Yields:
            Страницы — списки словарей-фильмов (до page_size штук).
        """
        query = """
            SELECT
                f.title,
                c.name        AS category,
                f.release_year,
                f.rating,
                f.description
            FROM film f
            LEFT JOIN film_category fc ON f.film_id      = fc.film_id
            LEFT JOIN category      c  ON fc.category_id = c.category_id
            WHERE f.title LIKE %s
            ORDER BY f.title
            LIMIT %s OFFSET %s
        """
        log.info("Поиск по ключевому слову: %r", keyword)
        yield from self._paginate(query, (f'%{keyword.strip()}%',))

    # ── Поиск по жанру и диапазону годов ──────────────────────────────────────

    def search_by_genre_year(
        self, genre: str, year_from: int, year_to: int
    ) -> Generator[list[dict], None, None]:
        """
        Генератор постраничного поиска по жанру и диапазону годов.

        Yields:
            Страницы — списки словарей-фильмов (до page_size штук).
        """
        query = """
            SELECT
                f.title,
                c.name        AS category,
                f.release_year,
                f.rating,
                f.description
            FROM film f
            JOIN film_category fc ON f.film_id      = fc.film_id
            JOIN category      c  ON fc.category_id = c.category_id
            WHERE c.name = %s
              AND f.release_year BETWEEN %s AND %s
            ORDER BY f.title
            LIMIT %s OFFSET %s
        """
        log.info("Поиск по жанру %r, годы %d–%d", genre, year_from, year_to)
        yield from self._paginate(query, (genre.strip(), year_from, year_to))
