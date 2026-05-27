"""
sql_requests.py — подключение к MySQL (Sakila) и поиск фильмов.

Принципы реализации:
  • Генераторы (_paginate) для постраничного обхода без загрузки всей БД в память.
  • Property (getter/setter) для защиты приватного атрибута __page_size.
  • Параметризованные запросы (%s) — защита от SQL-инъекций.
  • Каждый метод выполняет одну задачу (SRP / SOLID).
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import pymysql

# Путь к .env — всегда рядом с этим файлом, независимо от рабочей папки
load_dotenv(Path(__file__).parent / '.env')


# ── Конфигурация подключения ──────────────────────────────────────────────────

def _build_mysql_config() -> dict:
    """
    Читает параметры подключения из переменных окружения.

    Returns:
        dict: Словарь конфигурации для pymysql.connect().

    Raises:
        EnvironmentError: Если обязательные переменные не заданы в .env.
    """
    required = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    missing  = [k for k in required if not os.getenv(k)]
    if missing:
        env_path = Path(__file__).parent / ".env"
        hint = (
            f"Файл .env найден: {env_path}"
            if env_path.exists()
            else f"Файл .env НЕ найден: {env_path}"
        )
        raise EnvironmentError(
            f"Отсутствуют переменные окружения: {', '.join(missing)}. {hint}"
        )

    return {
        "host":        os.getenv("DB_HOST"),
        "port":        int(os.getenv("DB_PORT", "3306")),
        "user":        os.getenv("DB_USER"),
        "password":    os.getenv("DB_PASSWORD"),
        "database":    os.getenv("DB_NAME"),
        "charset":     "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        'connect_timeout': int(os.getenv('DB_CONNECT_TIMEOUT', '30')),
    }

    def _get_connection(self) -> pymysql.connections.Connection:
        """
        Создаёт и возвращает соединение с MySQL.

        Raises:
            ConnectionError: При ошибке подключения.
        """
        try:
            return pymysql.connect(**self.__config)
        except pymysql.MySQLError as exc:
            raise ConnectionError(
                f"Не удалось подключиться к MySQL: {exc}"
            ) from exc

    def _fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """
        Выполняет SELECT-запрос и возвращает все строки.

        Args:
            query:  SQL-запрос с %s-плейсхолдерами.
            params: Кортеж значений для подстановки (защита от инъекций).

        Returns:
            Список словарей-строк.

        Raises:
            ConnectionError: При сбое подключения.
            RuntimeError:    При ошибке выполнения запроса.
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.fetchall()
        except ConnectionError:
            raise
        except pymysql.MySQLError as exc:
            raise RuntimeError(f"Ошибка выполнения SQL-запроса: {exc}") from exc

    def _fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        """Выполняет SELECT-запрос и возвращает первую строку."""
        rows = self._fetch_all(query, params)
        return rows[0] if rows else None

# ── Метаданные (жанры, диапазон лет) ─────────────────────────────────────

get_genres = """SELECT name FROM category ORDER BY name"""

get_year_range = """
                 SELECT MIN(release_year) AS mn, MAX(release_year) AS mx FROM film"""

count_by_keyword = """SELECT COUNT(*) AS cnt FROM film WHERE title LIKE %s""",
            (f"%{keyword.strip()}%",)

count_by_genre_year = """
            SELECT COUNT(*) AS cnt
            FROM film f
            JOIN film_category fc ON f.film_id = fc.film_id
            JOIN category      c  ON fc.category_id = c.category_id
            WHERE c.name = %s
              AND f.release_year BETWEEN %s AND %s
            """

search_by_keyword = """
            SELECT
                f.title,
                c.name        AS category,
                f.release_year,
                f.rating,
                f.description
            FROM film f
            LEFT JOIN film_category fc ON f.film_id  = fc.film_id
            LEFT JOIN category      c  ON fc.category_id = c.category_id
            WHERE f.title LIKE %s
            ORDER BY f.title
            LIMIT %s OFFSET %s
        """


search_by_genre_year = """
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


