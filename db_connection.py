"""
db_connection.py — управление соединением с MySQL и выполнение запросов.

Конфигурация передаётся в __init__ как аргумент — класс не зависит от
глобальных переменных и может быть создан для любой базы данных.
"""

import os
from typing import Generator
import pymysql


class DBConnection:
    """
    Управляет подключением к MySQL и выполнением произвольных запросов.

    Базовый класс для MovieSearcher (sql_requests.py).
    Не содержит SQL — только механику работы с базой.

    Конфиг передаётся снаружи — можно создать несколько экземпляров
    для разных баз данных без изменения класса (принцип OCP).

    Атрибуты (приватные, доступны через property):
        __config    — словарь подключения pymysql.
        __page_size — количество строк на одну страницу результатов.
    """

    _MIN_PAGE: int = 1
    _MAX_PAGE: int = 100
    _DEF_PAGE: int = 10

    def __init__(self, config: dict) -> None:
        """
        Args:
            config: Словарь параметров pymysql.connect().
                    Обязательные ключи: host, user, password, database.
        """
        missing = [k for k in ('host', 'user', 'password', 'database')
                   if not config.get(k)]
        if missing:
            msg = (
                f"Не заданы параметры подключения: "
                f"{', '.join(k.upper() for k in missing)}. "
                f"Проверьте файл .env"
            )
            raise EnvironmentError(msg)

        self.__config: dict = config

        raw = int(os.getenv('DB_PAGE_SIZE', str(self._DEF_PAGE)))
        self.__page_size: int = max(self._MIN_PAGE, min(raw, self._MAX_PAGE))

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def page_size(self) -> int:
        """Количество фильмов на одной странице результатов."""
        return self.__page_size

    @page_size.setter
    def page_size(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError("page_size должен быть целым числом")
        if not (self._MIN_PAGE <= value <= self._MAX_PAGE):
            raise ValueError(
                f"page_size должен быть от {self._MIN_PAGE} до {self._MAX_PAGE}"
            )
        self.__page_size = value

    # ── Подключение ───────────────────────────────────────────────────────────

    def _get_connection(self) -> pymysql.connections.Connection:
        """
        Открывает и возвращает соединение с MySQL.

        Raises:
            ConnectionError: При недоступности сервера.
        """
        try:
            return pymysql.connect(**self.__config)
        except pymysql.MySQLError as exc:
            raise ConnectionError(
                f"Не удалось подключиться к MySQL: {exc}"
            ) from exc

    # ── Выполнение запросов ───────────────────────────────────────────────────

    def _fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """
        Выполняет SELECT-запрос и возвращает все строки.

        Args:
            query:  SQL с %s-плейсхолдерами (защита от инъекций).
            params: Значения для подстановки.
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.fetchall()
        except ConnectionError:
            raise
        except pymysql.MySQLError as exc:
            raise RuntimeError(f"Ошибка выполнения запроса: {exc}") from exc

    def _fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        """Выполняет SELECT-запрос и возвращает первую строку (или None)."""
        rows = self._fetch_all(query, params)
        return rows[0] if rows else None

    # ── Пагинация ─────────────────────────────────────────────────────────────

    def _paginate(
        self, query: str, base_params: tuple
    ) -> Generator[list[dict], None, None]:
        """
        Универсальный генератор постраничного обхода результатов.

        Ожидает, что query заканчивается «LIMIT %s OFFSET %s».
        Останавливается когда страница пустая или короче page_size.

        Yields:
            Страницы — списки словарей-строк.
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
