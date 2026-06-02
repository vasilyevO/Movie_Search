"""
mongo_log_search.py — MongoDB base connection class and search request logging.

MongoBase  — base class reused in log_search.py (DRY principle).
SearchLogger — writes each search request to a MongoDB collection.

Parameter normalisation:
  - Strings are lowercased and stripped (.strip().lower()).
  - Ensures consistent deduplication when aggregating statistics.
"""

from datetime import datetime, timezone
import pymongo
import pymongo.errors

from logger import get_logger

log = get_logger(__name__)


class MongoBase:
    """
    Manages the MongoDB client lifecycle (lazy connection).

    Base class for SearchLogger and SearchStats.
    Connection parameters are injected via __init__ — the class
    is not coupled to global variables and supports multiple instances
    pointing at different databases (OCP).

    Args:
        config: Dictionary with keys: uri, db_name, collection.
    """

    def __init__(self, config: dict) -> None:
        self.__uri:        str                        = config['uri']
        self.__db_name:    str                        = config['db_name']
        self.__collection: str                        = config['collection']
        self.__client:     pymongo.MongoClient | None = None

    # ── Read-only properties ──────────────────────────────────────────────────

    @property
    def db_name(self) -> str:
        """Name of the MongoDB database."""
        return self.__db_name

    @property
    def collection_name(self) -> str:
        """Name of the MongoDB collection."""
        return self.__collection

    # ── Connection ────────────────────────────────────────────────────────────

    def _get_collection(self) -> pymongo.collection.Collection:
        """
        Returns the collection, creating the client on first call.

        Raises:
            ConnectionError: On timeout or connection failure.
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
            log.error("MongoDB connection timeout: %s", exc)
            raise ConnectionError(f"Тайм-аут MongoDB: {exc}") from exc
        except pymongo.errors.ConnectionFailure as exc:
            log.error("MongoDB connection failure: %s", exc)
            raise ConnectionError(f"Ошибка подключения к MongoDB: {exc}") from exc
        except pymongo.errors.ConfigurationError as exc:
            log.error("MongoDB invalid URI: %s", exc)
            raise ConnectionError(f"Некорректный URI MongoDB: {exc}") from exc

    def close(self) -> None:
        """Closes the MongoDB client."""
        if self.__client is not None:
            self.__client.close()
            self.__client = None

    def __del__(self) -> None:
        self.close()


class SearchLogger(MongoBase):
    """
    Writes search events to a MongoDB collection.

    Document example:
        {
            "timestamp":     "2026-05-28_17:21:16",
            "search_type":   "keyword",
            "params":        {"keyword": "matrix"},
            "results_count": 3
        }

    Args:
        config: Dictionary with keys: uri, db_name, collection.
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    @staticmethod
    def _normalize_params(params: dict) -> dict:
        """
        Normalises string parameter values: strip + lower.

        Ensures identical queries typed in different cases
        are grouped correctly during aggregation.

        Args:
            params: Raw search parameter dictionary.

        Returns:
            New dictionary with normalised string values.
        """
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
        Persists a search request record in MongoDB.

        Args:
            search_type:   Search type — 'keyword' or 'genre_year'.
            params:        Search parameter dictionary.
            results_count: Total number of matching films found.

        Raises:
            ConnectionError: If MongoDB is unreachable.
            RuntimeError:    If the insert operation fails.
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
                "MongoDB write error | search_type=%s | params=%s | %s",
                search_type, params, exc,
            )
            raise RuntimeError(f"Ошибка записи в MongoDB: {exc}") from exc
