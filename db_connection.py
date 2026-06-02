"""
db_connection.py — MySQL connection management and query execution.

Responsibilities:
  - Storing the connection configuration.
  - Opening connections via pymysql.connect().
  - Generic query execution methods (_fetch_all, _fetch_one).
  - Generic paginated result generator (_paginate).

Contains no SQL queries — that is the responsibility of sql_requests.py.
"""

import os
from typing import Generator
import pymysql

from logger import get_logger

log = get_logger(__name__)


class DBConnection:
    """
    Manages MySQL connections and executes arbitrary queries.

    Base class for MovieSearcher (sql_requests.py).
    Contains no SQL — only the database interaction mechanics.

    The configuration is injected via __init__ so the class is not
    coupled to global variables and multiple instances can be created
    for different databases without modifying the class (OCP).

    Private attributes (accessible via properties):
        __config    — pymysql connection dictionary.
        __page_size — number of rows per results page.

    Args:
        config: Dictionary of pymysql.connect() parameters.
                Required keys: host, user, password, database.
    """

    _MIN_PAGE: int = 1
    _MAX_PAGE: int = 100
    _DEF_PAGE: int = 10

    def __init__(self, config: dict) -> None:
        missing = [k for k in ('host', 'user', 'password', 'database')
                   if not config.get(k)]
        if missing:
            msg = (
                f"Missing connection parameters: "
                f"{', '.join(k.upper() for k in missing)}. "
                f"Check your .env file."
            )
            log.error(msg)
            raise EnvironmentError(msg)

        self.__config: dict = config

        raw = int(os.getenv('DB_PAGE_SIZE', str(self._DEF_PAGE)))
        self.__page_size: int = max(self._MIN_PAGE, min(raw, self._MAX_PAGE))

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def page_size(self) -> int:
        """Number of films per results page."""
        return self.__page_size

    @page_size.setter
    def page_size(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError("page_size must be an integer")
        if not (self._MIN_PAGE <= value <= self._MAX_PAGE):
            raise ValueError(
                f"page_size must be between {self._MIN_PAGE} and {self._MAX_PAGE}"
            )
        self.__page_size = value

    # ── Connection ────────────────────────────────────────────────────────────

    def _get_connection(self) -> pymysql.connections.Connection:
        """
        Opens and returns a MySQL connection.

        Raises:
            ConnectionError: If the server is unreachable.
        """
        try:
            return pymysql.connect(**self.__config)
        except pymysql.MySQLError as exc:
            log.error("MySQL connection error: %s", exc)
            raise ConnectionError(
                f"Не удалось подключиться к MySQL: {exc}"
            ) from exc

    # ── Query execution ───────────────────────────────────────────────────────

    def _fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """
        Executes a SELECT query and returns all rows.

        Args:
            query:  SQL with %s placeholders (injection-safe).
            params: Values to substitute.

        Returns:
            List of row dictionaries.

        Raises:
            ConnectionError: Propagated from _get_connection().
            RuntimeError:    On query execution error.
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.fetchall()
        except ConnectionError:
            raise
        except pymysql.MySQLError as exc:
            log.error("SQL query error: %s | query: %s", exc, query)
            raise RuntimeError(f"Ошибка выполнения запроса: {exc}") from exc

    def _fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        """Executes a SELECT query and returns the first row (or None)."""
        rows = self._fetch_all(query, params)
        return rows[0] if rows else None

    # ── Pagination ────────────────────────────────────────────────────────────

    def _paginate(
        self, query: str, base_params: tuple
    ) -> Generator[list[dict], None, None]:
        """
        Universal paginated result generator.

        Expects the query to end with 'LIMIT %s OFFSET %s'.
        Appends page_size and offset to base_params on each iteration.
        Stops when the page is empty or shorter than page_size.

        Args:
            query:       SQL query ending with 'LIMIT %s OFFSET %s'.
            base_params: Core parameter tuple (without LIMIT/OFFSET).

        Yields:
            Pages — lists of row dictionaries.
        """
        offset = 0
        while True:
            page = self._fetch_all(
                query, base_params + (self.__page_size, offset)
            )
            if not page:
                break
            yield page
            if len(page) < self.__page_size:
                break
            offset += self.__page_size
