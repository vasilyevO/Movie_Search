"""
log_search.py — статистика поисковых запросов из MongoDB.

SearchStats наследует MongoBase и прокидывает параметры подключения
через super().__init__() — логика соединения не дублируется (DRY).
"""

import pymongo.errors

from log_search_hist import MongoBase

class SearchStats(MongoBase):
    """
    Читает агрегированную статистику из коллекции поисковых запросов.
    Наследует MongoBase для переиспользования логики подключения.

    Args:
        config: Словарь с ключами uri, db_name, collection.
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    def get_popular_searches(self, limit: int = 5) -> list[dict]:
        """
        Возвращает самые часто повторяющиеся запросы.

        Группирует по (search_type, params), считает частоту.
        """
        pipeline = [
            {
                '$group': {
                    '_id': {
                        'search_type': '$search_type',
                        'params':      '$params',
                    },
                    'frequency':     {'$sum': 1},
                    'results_count': {'$last': '$results_count'},
                    'timestamp':     {'$last': '$timestamp'},
                }
            },
            {'$sort': {'frequency': -1}},
            {'$limit': limit},
            {
                '$project': {
                    '_id':           0,
                    'search_type':   '$_id.search_type',
                    'params':        '$_id.params',
                    'frequency':     1,
                    'results_count': 1,
                    'timestamp':     1,
                }
            },
        ]
        return self._run_pipeline(pipeline)

    def get_recent_unique_searches(self, limit: int = 5) -> list[dict]:
        """
        Возвращает последние уникальные запросы.

        Уникальность — по паре (search_type, params).
        Для каждой пары берётся самая последняя запись.
        """
        pipeline = [
            {'$sort': {'timestamp': -1}},
            {
                '$group': {
                    '_id': {
                        'search_type': '$search_type',
                        'params':      '$params',
                    },
                    'timestamp':     {'$first': '$timestamp'},
                    'results_count': {'$first': '$results_count'},
                }
            },
            {'$sort': {'timestamp': -1}},
            {'$limit': limit},
            {
                '$project': {
                    '_id':           0,
                    'search_type':   '$_id.search_type',
                    'params':        '$_id.params',
                    'timestamp':     1,
                    'results_count': 1,
                }
            },
        ]
        return self._run_pipeline(pipeline)

    def _run_pipeline(self, pipeline: list[dict]) -> list[dict]:
        """Выполняет агрегационный pipeline и возвращает результат."""
        try:
            return list(self._get_collection().aggregate(pipeline))
        except ConnectionError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Ошибка чтения статистики из MongoDB: {exc}"
            ) from exc
