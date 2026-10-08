from pathlib import Path

from psycopg_pool import ConnectionPool

from ..config import Config, pg_schema
from .base import ADDED_COLUMNS, COLUMNS, Store

_COLS = ", ".join(COLUMNS)
_INSERT = f"INSERT INTO entries({_COLS}) VALUES({', '.join('%s' for _ in COLUMNS)})"


class PostgresStore(Store):
    backend = "postgres"

    def __init__(self) -> None:
        schema = pg_schema()
        sslmode = "disable" if Config.DATABASE_SSL == "disable" else "require"
        # search_path pinned for the connection's lifetime via libpq options.
        # Requires a session-mode connection (Supabase Session pooler, :5432).
        conninfo = (
            f"{Config.DATABASE_URL}"
            f"?sslmode={sslmode}&options=-c%20search_path%3D{schema}"
        )
        self._pool = ConnectionPool(conninfo, min_size=1, max_size=Config.PGPOOL_MAX, open=True)
        ddl = (Path(__file__).resolve().parent.parent / "schema.sql").read_text()
        with self._pool.connection() as conn:
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
            conn.execute(ddl)
            for col, decl in ADDED_COLUMNS:
                conn.execute(f"ALTER TABLE entries ADD COLUMN IF NOT EXISTS {col} {decl}")

    def insert_entry(self, row):
        with self._pool.connection() as conn:
            conn.execute(_INSERT, tuple(row[c] for c in COLUMNS))

    def list_entries(self, since):
        with self._pool.connection() as conn:
            rows = conn.execute(
                f"SELECT {_COLS} FROM entries WHERE created_at >= %s ORDER BY created_at", (since,)
            ).fetchall()
        return [dict(zip(COLUMNS, r)) for r in rows]

    def delete_entry(self, id):
        with self._pool.connection() as conn:
            cur = conn.execute("DELETE FROM entries WHERE id=%s", (id,))
            return cur.rowcount
