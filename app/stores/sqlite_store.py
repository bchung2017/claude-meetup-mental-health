import sqlite3
import threading
from pathlib import Path

from ..config import Config
from .base import COLUMNS, Store, table_spec

_COLS = ", ".join(COLUMNS)
_INSERT = f"INSERT INTO entries({_COLS}) VALUES({', '.join('?' for _ in COLUMNS)})"


def migrate(db: sqlite3.Connection) -> None:
    """Bring a pre-existing entries table up to the current schema (idempotent)."""
    have = {r[1] for r in db.execute("PRAGMA table_info(entries)")}
    if "adherence" not in have:
        db.execute("ALTER TABLE entries ADD COLUMN adherence INTEGER NOT NULL DEFAULT 0")
    if "meds_taken" in have:  # short-lived boolean, folded into the 0-100 score
        db.execute("UPDATE entries SET adherence = meds_taken * 100")
        db.execute("ALTER TABLE entries DROP COLUMN meds_taken")
    db.commit()


class SqliteStore(Store):
    backend = "sqlite"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(Config.SQLITE_PATH, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL;")
        ddl = (Path(__file__).resolve().parent.parent / "schema.sql").read_text()
        self._db.executescript(ddl)
        migrate(self._db)

    def insert_entry(self, row):
        with self._lock:
            self._db.execute(_INSERT, tuple(row[c] for c in COLUMNS))
            self._db.commit()

    def list_entries(self, since):
        with self._lock:
            rows = self._db.execute(
                f"SELECT {_COLS} FROM entries WHERE created_at >= ? ORDER BY created_at", (since,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_entry(self, id):
        with self._lock:
            cur = self._db.execute("DELETE FROM entries WHERE id=?", (id,))
            self._db.commit()
            return cur.rowcount

    def insert_rows(self, table, rows):
        cols, _ = table_spec(table)
        sql = f"INSERT OR IGNORE INTO {table}({', '.join(cols)}) VALUES({', '.join('?' for _ in cols)})"
        with self._lock:
            self._db.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
            self._db.commit()

    def list_rows(self, table, patient_id=None):
        cols, order = table_spec(table)
        sql = f"SELECT {', '.join(cols)} FROM {table}"
        params = ()
        if patient_id is not None:
            sql += " WHERE patient_id = ?"
            params = (patient_id,)
        with self._lock:
            rows = self._db.execute(f"{sql} ORDER BY {order}", params).fetchall()
        return [dict(r) for r in rows]
