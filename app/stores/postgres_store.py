from pathlib import Path

from psycopg_pool import ConnectionPool

from ..config import Config, pg_schema
from .base import COLUMNS, Store, table_spec

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

    def insert_rows(self, table, rows):
        cols, _ = table_spec(table)
        sql = (
            f"INSERT INTO {table}({', '.join(cols)}) VALUES({', '.join('%s' for _ in cols)}) "
            "ON CONFLICT DO NOTHING"
        )
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])

    def list_rows(self, table, patient_id=None):
        cols, order = table_spec(table)
        sql = f"SELECT {', '.join(cols)} FROM {table}"
        params = ()
        if patient_id is not None:
            sql += " WHERE patient_id = %s"
            params = (patient_id,)
        with self._pool.connection() as conn:
            rows = conn.execute(f"{sql} ORDER BY {order}", params).fetchall()
        return [dict(zip(cols, r)) for r in rows]
