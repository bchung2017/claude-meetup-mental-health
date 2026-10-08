import sqlite3
import threading

from ..config import Config
from .base import (CHILD_TABLES, COLUMNS, LEGACY_TABLES, ORDER_BY, REFERENCE_TABLES,
                   SCHEMA_PATH, TABLES, Store, check_relation)

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
        self._db.execute("PRAGMA foreign_keys=ON;")
        self._reset_legacy()
        self._db.executescript(SCHEMA_PATH.read_text())
        migrate(self._db)
        self._db.commit()

    def _has_table(self, name: str) -> bool:
        return self._db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    def _reset_legacy(self) -> None:
        if self._has_table("patients") and not self._has_table("data_sources"):
            for t in LEGACY_TABLES:
                self._db.execute(f"DROP TABLE IF EXISTS {t}")
            self._db.commit()

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
        if not rows:
            return
        check_relation(table)
        cols = tuple(rows[0])
        sql = f"INSERT OR IGNORE INTO {table}({', '.join(cols)}) VALUES({', '.join('?' for _ in cols)})"
        with self._lock:
            self._db.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
            self._db.commit()

    def list_rows(self, table, patient_id=None):
        check_relation(table)
        sql, params = f"SELECT * FROM {table}", ()
        if patient_id is not None:
            sql, params = sql + " WHERE patient_id = ?", (patient_id,)
        if table in ORDER_BY:
            sql += f" ORDER BY {ORDER_BY[table]}"
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, params).fetchall()]

    def delete_patient_rows(self, patient_id):
        with self._lock:
            self._db.execute(
                "DELETE FROM assessment_items WHERE assessment_id IN (SELECT assessment_id FROM assessments WHERE patient_id=?)",
                (patient_id,))
            self._db.execute(
                "DELETE FROM mood_checkin_tags WHERE checkin_id IN (SELECT checkin_id FROM mood_checkins WHERE patient_id=?)",
                (patient_id,))
            self._db.execute(
                "DELETE FROM narrative_themes WHERE narrative_id IN (SELECT narrative_id FROM narratives WHERE patient_id=?)",
                (patient_id,))
            for t in reversed(TABLES):
                if t in REFERENCE_TABLES or t in CHILD_TABLES:
                    continue
                self._db.execute(f"DELETE FROM {t} WHERE patient_id=?", (patient_id,))
            self._db.commit()
