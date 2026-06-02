"""
main.py — the entry point for building and running the application.

It is responsible only for:
  • Loading the configuration from .env.
  • Constructing connection configurations.
  • Creating component instances.
  • Passing control to run_menu().

To run:
    python main.py
"""

import os
import sys
from dotenv import load_dotenv

# ── Load the .env file FIRST, before importing any project modules ────────────
load_dotenv('.env')

import pymysql
from logger import get_logger
from sql_requests import MovieSearcher
from mongo_log_search import SearchLogger
from log_search import SearchStats
from menu import run_menu
from formatter_UI import InfoMessage

log = get_logger(__name__)


# ── Creating connection configurations ───────────────────────────────────────────

def build_mysql_config() -> dict:
    """
    Retrieves a MySQL configuration dictionary from environment variables.

    Returns:
        A dictionary of parameters for `pymysql.connect()`.
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
    Reads MongoDB settings from environment variables.

    Returns:
        A dictionary with the keys `uri`, `db_name` and `collection` —
        identical to `build_mysql_config()`.
    """
    return {
        'uri':        os.getenv('MONGO_URI', ''),
        'db_name':    os.getenv('MONGO_DB',  'ich_edit'),
        'collection': os.getenv('MONGO_COLLECTION', 'final_project_121225_oleg_v'),
    }


# ── Точка входа ───────────────────────────────────────────────────────────────

def main() -> None:
    """Creates components and passes control to run_menu()."""
    try:
        searcher = MovieSearcher(build_mysql_config())
    except EnvironmentError as exc:
        log.error("Ошибка конфигурации MySQL при запуске: %s", exc)
        print(InfoMessage(f"Ошибка конфигурации: {exc}", "error"))
        sys.exit(1)

    logger = SearchLogger(build_mongo_config())
    stats  = SearchStats(build_mongo_config())

    run_menu(searcher, logger, stats)


if __name__ == "__main__":
    main()
