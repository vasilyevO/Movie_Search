"""
log_search_hist.py — базовый класс MongoDB-соединения и логирование запросов.

Параметры подключения передаются в __init__ — класс не зависит от
глобальных переменных и может быть подключён к любой MongoDB-базе.
"""

from datetime import datetime, timezone
import pymongo
import pymongo.errors

from logger import get_logger

log = get_logger(__name__)


class MongoBase:
    """
    Управляет жизненным циклом MongoDB-клиента (ленивое подключение).

    Базовый класс для SearchLogger и SearchStats (принцип DRY).
    Параметры подключения принимаются снаружи — можно создать несколько
    экземпляров для разных баз без изменения класса (принцип OCP).

    Args:
        config: Словарь с ключами uri, db_name, collection.
    """

    def __init__(self, config: dict) -> None:
        self.__uri:        str                        = config['uri']
        self.__db_name:    str                        = config['db_name']
        self.__collection: str                        = config['collection']
        self.__client:     pymongo.MongoClient | None = None

    # ── Properties (только чтение) ────────────────────────────────────────────

    @property
    def db_name(self) -> str:
        return self.__db_name

    @property
    def collection_name(self) -> str:
        return self.__collection

    # ── Подключение ───────────────────────────────────────────────────────────

    def _get_collection(self) -> pymongo.collection.Collection:
        """
        Возвращает коллекцию, создавая клиент при первом обращении.

        Raises:
            ConnectionError: При сбое или таймауте подключения.
        """
        try:
            if self.__client is None:
                self.__client = pymongo.MongoClient(
                    self.__uri,
                    serverSelectionTimeoutMS=5_000,
                )
                self.__client.admin.command('ping')
            return self.__client[self.__db_name][self.__collection]
        except pymongo.errors.ServerSelectionTimeoutError as exc:
            log.error("Тайм-аут подключения к MongoDB: %s", exc)
            raise ConnectionError(f"Тайм-аут MongoDB: {exc}") from exc
        except pymongo.errors.ConnectionFailure as exc:
            log.error("Ошибка подключения к MongoDB: %s", exc)
            raise ConnectionError(f"Ошибка подключения к MongoDB: {exc}") from exc
        except pymongo.errors.ConfigurationError as exc:
            log.error("Некорректный URI MongoDB: %s", exc)
            raise ConnectionError(f"Некорректный URI MongoDB: {exc}") from exc

    def close(self) -> None:
        """Закрывает клиент MongoDB."""
        if self.__client is not None:
            self.__client.close()
            self.__client = None

    def __del__(self) -> None:
        self.close()


class SearchLogger(MongoBase):
    """
    Записывает поисковые события в MongoDB-коллекцию.

    Пример документа:
        {
            "timestamp":     "2025-05-01T15:34:00",
            "search_type":   "keyword",
            "params":        {"keyword": "matrix"},
            "results_count": 3
        }
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    @staticmethod
    def _normalize_params(params: dict) -> dict:
        """Нормализует строковые параметры: strip + lower."""
        return {
            key: value.strip().lower() if isinstance(value, str) else value
            for key, value in params.items()
        }

    def log_search(
        self,
        search_type: str,
        params: dict,
        results_count: int,
    ) -> None:
        """
        Сохраняет запись о поисковом запросе в MongoDB.

        Args:
            search_type:   'keyword' или 'genre_year'.
            params:        Словарь параметров поиска.
            results_count: Количество найденных фильмов.
        """
        document = {
            'timestamp':     datetime.now(timezone.utc).strftime('%Y-%m-%d_%H:%M:%S'),
            'search_type':   search_type.strip(),
            'params':        self._normalize_params(params),
            'results_count': max(0, int(results_count)),
        }
        try:
            self._get_collection().insert_one(document)
        except pymongo.errors.PyMongoError as exc:
            log.error(
                "Ошибка записи в MongoDB | search_type=%s | params=%s | %s",
                search_type, params, exc,
            )
            raise RuntimeError(f"Ошибка записи в MongoDB: {exc}") from exc
