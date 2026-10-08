from functools import lru_cache

from ..config import Config
from .base import Store


@lru_cache(maxsize=1)
def get_store() -> Store:
    if Config.USE_POSTGRES:
        from .postgres_store import PostgresStore

        return PostgresStore()
    from .sqlite_store import SqliteStore

    return SqliteStore()
