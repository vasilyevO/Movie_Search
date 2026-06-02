"""
log_search.py — search request statistics from MongoDB.

SearchStats inherits MongoBase — connection logic is not duplicated (DRY).
"""

import pymongo.errors

from mongo_log_search import MongoBase
from logger import get_logger

log = get_logger(__name__)


class SearchStats(MongoBase):
    """
    Reads aggregated statistics from the search history collection.

    Inherits MongoBase to reuse connection management.

    Args:
        config: Dictionary with keys: uri, db_name, collection.
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    def get_popular_searches(self, limit: int = 5) -> list[dict]:
        """
        Returns the most frequently repeated search queries.

        Groups by (search_type, params) and counts occurrences (frequency).

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of dicts with keys: search_type, params,
            frequency, results_count, timestamp.

        Raises:
            ConnectionError: If MongoDB is unreachable.
            RuntimeError:    If the aggregation pipeline fails.
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
        Returns the most recent unique search queries.

        Uniqueness is determined by the (search_type, params) pair.
        For each unique pair the latest record is selected.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of dicts with keys: search_type, params,
            results_count, timestamp.

        Raises:
            ConnectionError: If MongoDB is unreachable.
            RuntimeError:    If the aggregation pipeline fails.
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
            # Re-sort after $group — ordering is not preserved
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
        """
        Executes a MongoDB aggregation pipeline and returns the result.

        Args:
            pipeline: List of aggregation stage dictionaries.

        Returns:
            List of result documents.

        Raises:
            ConnectionError: Propagated from _get_collection().
            RuntimeError:    On any other pipeline execution error.
        """
        try:
            return list(self._get_collection().aggregate(pipeline))
        except ConnectionError:
            raise
        except Exception as exc:
            log.error("MongoDB aggregation error: %s", exc)
            raise RuntimeError(
                f"Ошибка чтения статистики из MongoDB: {exc}"
            ) from exc
