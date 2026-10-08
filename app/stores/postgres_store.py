from psycopg_pool import ConnectionPool

from ..config import Config, pg_schema
from .base import (CHILD_TABLES, COLUMNS, LEGACY_TABLES, ORDER_BY, REFERENCE_TABLES,
                   SCHEMA_PATH, TABLES, Store, check_relation)

_COLS = ", ".join(COLUMNS)
_INSERT = f"INSERT INTO entries({_COLS}) VALUES({', '.join('%s' for _ in COLUMNS)})"


def migrate(conn, schema: str) -> None:
    """Bring a pre-existing entries table up to the current schema (idempotent)."""
    conn.execute("ALTER TABLE entries ADD COLUMN IF NOT EXISTS adherence INTEGER NOT NULL DEFAULT 0")
    had_bool = conn.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = 'entries' AND column_name = 'meds_taken'",
        (schema,),
    ).fetchone()
    if had_bool:  # short-lived boolean, folded into the 0-100 score
        conn.execute("UPDATE entries SET adherence = meds_taken * 100")
        conn.execute("ALTER TABLE entries DROP COLUMN meds_taken")


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
        with self._pool.connection() as conn:
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
            self._reset_legacy(conn, schema)
            conn.execute(SCHEMA_PATH.read_text())
            migrate(conn, schema)

    @staticmethod
    def _reset_legacy(conn, schema: str) -> None:
        have = {r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (schema,)
        ).fetchall()}
        if "patients" in have and "data_sources" not in have:
            for t in LEGACY_TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {t}")

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
        if not rows:
            return
        check_relation(table)
        cols = tuple(rows[0])
        sql = (
            f"INSERT INTO {table}({', '.join(cols)}) VALUES({', '.join('%s' for _ in cols)}) "
            "ON CONFLICT DO NOTHING"
        )
        with self._pool.connection() as conn, conn.cursor() as cur:
            cur.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])

    def list_rows(self, table, patient_id=None):
        check_relation(table)
        sql, params = f"SELECT * FROM {table}", ()
        if patient_id is not None:
            sql, params = sql + " WHERE patient_id = %s", (patient_id,)
        if table in ORDER_BY:
            sql += f" ORDER BY {ORDER_BY[table]}"
        with self._pool.connection() as conn:
            cur = conn.execute(sql, params)
            names = [d.name for d in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]

    def delete_patient_rows(self, patient_id):
        with self._pool.connection() as conn:
            conn.execute(
                "DELETE FROM assessment_items WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE patient_id=%s)",
                (patient_id,))
            conn.execute(
                "DELETE FROM mood_checkin_tags WHERE checkin_id IN (SELECT checkin_id FROM mood_checkins WHERE patient_id=%s)",
                (patient_id,))
            conn.execute(
                "DELETE FROM narrative_themes WHERE narrative_id IN (SELECT narrative_id FROM narratives WHERE patient_id=%s)",
                (patient_id,))
            for t in reversed(TABLES):
                if t in REFERENCE_TABLES or t in CHILD_TABLES:
                    continue
                conn.execute(f"DELETE FROM {t} WHERE patient_id=%s", (patient_id,))
