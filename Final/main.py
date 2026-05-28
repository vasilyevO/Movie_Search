"""
main.py — точка сборки и запуска приложения.

Отвечает только за:
  • Загрузку .env и построение конфигов подключений.
  • Создание компонентов и передачу им конфигов.
  • Запуск цикла меню через run_menu().

Не содержит логики поиска, форматирования и работы с меню.
"""

import os
import sys
from dotenv import load_dotenv

# Загружаем .env первым делом — до любых импортов модулей проекта
load_dotenv('.env')

import pymysql
from logger import get_logger
from sql_requests import MovieSearcher
from log_search_hist import SearchLogger
from log_search import SearchStats
from menu import run_menu

log = get_logger(__name__)


# ── Построение конфигов ───────────────────────────────────────────────────────

def build_mysql_config() -> dict:
    """
    Собирает конфиг MySQL из переменных окружения.

    Returns:
        Словарь параметров для pymysql.connect().
    """
    return {
        'host':            os.getenv('DB_HOST'),
        'port':            int(os.getenv('DB_PORT', '3306')),
        'user':            os.getenv('DB_USER'),
        'password':        os.getenv('DB_PASSWORD'),
        'database':        os.getenv('DB_NAME'),
        'charset':         'utf8mb4',
        'cursorclass':     pymysql.cursors.DictCursor,
        'connect_timeout': int(os.getenv('DB_CONNECT_TIMEOUT', '30')),
    }


def build_mongo_config() -> dict:
    """
    Собирает конфиг MongoDB из переменных окружения.

    Returns:
        Словарь с ключами uri, db_name, collection.
    """
    return {
        'uri':        os.getenv('MONGO_URI', ''),
        'db_name':    os.getenv('MONGO_DB',  'ich_edit'),
        'collection': os.getenv('MONGO_COLLECTION', 'final_project_121225_oleg_v'),
    }


# ── Точка входа ───────────────────────────────────────────────────────────────

def main() -> None:
    """Создаёт компоненты и запускает цикл меню."""
    try:
        searcher = MovieSearcher(build_mysql_config())
    except EnvironmentError as exc:
        log.error("Ошибка конфигурации MySQL: %s", exc)
        print(f"Ошибка конфигурации: {exc}")
        sys.exit(1)

    logger = SearchLogger(build_mongo_config())
    stats  = SearchStats(build_mongo_config())

    run_menu(searcher, logger, stats)


if __name__ == "__main__":
    main()
