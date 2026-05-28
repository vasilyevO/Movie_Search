"""
main.py — точка входа демо-версии.

Запуск:
    python main.py

Структура демо-папки:
    main.py            — сборка конфигов и запуск
    menu.py            — меню и взаимодействие с пользователем
    db_connection.py   — подключение к MySQL
    sql_requests.py    — SQL-запросы и поиск фильмов
    log_search_hist.py — запись истории в MongoDB
    log_search.py      — чтение статистики из MongoDB
    .env               — параметры подключения
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv('.env')

import pymysql
from sql_requests import MovieSearcher
from log_search_hist import SearchLogger
from log_search import SearchStats
from menu import run_menu


def build_mysql_config() -> dict:
    """Собирает конфиг MySQL из переменных окружения."""
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
    """Собирает конфиг MongoDB из переменных окружения."""
    return {
        'uri':        os.getenv('MONGO_URI', ''),
        'db_name':    os.getenv('MONGO_DB',  'ich_edit'),
        'collection': os.getenv('MONGO_COLLECTION', 'final_project_121225_oleg_v'),
    }


def main() -> None:
    """Создаёт компоненты и запускает меню."""
    try:
        searcher = MovieSearcher(build_mysql_config())
    except EnvironmentError as exc:
        print(f"Ошибка конфигурации: {exc}")
        sys.exit(1)

    logger = SearchLogger(build_mongo_config())
    stats  = SearchStats(build_mongo_config())

    run_menu(searcher, logger, stats)


if __name__ == "__main__":
    main()
