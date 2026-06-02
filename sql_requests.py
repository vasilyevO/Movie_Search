"""
sql_requests.py — SQL queries and film search logic for the Sakila database.

Responsibilities:
  - SQL query strings.
  - Business logic for film search (by keyword, by genre and year range).
  - Metadata retrieval (genres, year range, result counts).

Contains no connection logic — that is the responsibility of db_connection.py.
Called from main.py via menu.py.
"""

from typing import Generator

from db_connection import DBConnection
from logger import get_logger

log = get_logger(__name__)


class MovieSearcher(DBConnection):
    """
    Searches for films in the Sakila MySQL database.

    Inherits DBConnection — receives _fetch_all, _fetch_one, _paginate
    without duplicating connection logic (DRY principle).

    All SQL queries use %s placeholders (SQL injection protection).
    Paginated traversal is implemented via generators (memory efficiency).

    Args:
        config: pymysql.connect() parameter dictionary from main.py.
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    # ── Metadata ──────────────────────────────────────────────────────────────

    def get_genres(self) -> list[str]:
        """
        Returns a sorted list of genre names from the category table.

        Returns:
            List of genre name strings.
        """
        query = "SELECT name FROM category ORDER BY name"
        rows = self._fetch_all(query)
        return [row['name'] for row in rows]

    def get_year_range(self) -> tuple[int, int]:
        """
        Returns the minimum and maximum film release years.

        Returns:
            Tuple (min_year, max_year).
        """
        query = (
            "SELECT MIN(release_year) AS mn, MAX(release_year) AS mx "
            "FROM film"
        )
        row = self._fetch_one(query)
        if row and row['mn'] is not None:
            return int(row['mn']), int(row['mx'])
        return 0, 0

    # ── Result counts (for accurate logging) ─────────────────────────────────

    def count_by_keyword(self, keyword: str) -> int:
        """
        Returns the total number of films matching the keyword.

        Args:
            keyword: Search word (% wildcards are added internally).
        """
        query = "SELECT COUNT(*) AS cnt FROM film WHERE title LIKE %s"
        row = self._fetch_one(query, (f'%{keyword.strip()}%',))
        return int(row['cnt']) if row else 0

    def count_by_genre_year(
        self, genre: str, year_from: int, year_to: int
    ) -> int:
        """
        Returns the total number of films matching genre and year range.

        Args:
            genre:     Exact genre name (category.name).
            year_from: Lower year bound (inclusive).
            year_to:   Upper year bound (inclusive).
        """
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

    # ── Keyword search ────────────────────────────────────────────────────────

    def search_by_keyword(
        self, keyword: str
    ) -> Generator[list[dict], None, None]:
        """
        Paginated generator for film search by partial title match.

        Args:
            keyword: Word to search for in the title field.

        Yields:
            Pages — lists of film dictionaries (up to page_size each).
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
        log.info("Keyword search: %r", keyword)
        yield from self._paginate(query, (f'%{keyword.strip()}%',))

    # ── Genre + year range search ─────────────────────────────────────────────

    def search_by_genre_year(
        self, genre: str, year_from: int, year_to: int
    ) -> Generator[list[dict], None, None]:
        """
        Paginated generator for film search by genre and year range.

        Args:
            genre:     Exact genre name (category.name match).
            year_from: Lower year bound (inclusive).
            year_to:   Upper year bound (inclusive).

        Yields:
            Pages — lists of film dictionaries (up to page_size each).
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
        log.info("Genre/year search: %r %d–%d", genre, year_from, year_to)
        yield from self._paginate(query, (genre.strip(), year_from, year_to))
