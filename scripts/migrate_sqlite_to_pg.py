import os
import sqlite3
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import Config, pg_schema  # noqa: E402
from app.stores.base import COLUMNS  # noqa: E402
from app.stores.postgres_store import migrate as migrate_pg  # noqa: E402
from app.stores.sqlite_store import migrate as migrate_sqlite  # noqa: E402


def main() -> None:
    src_path = sys.argv[1] if len(sys.argv) > 1 else Config.SQLITE_PATH
    dsn = os.environ["DATABASE_URL"]
    schema = pg_schema()
    ddl = (Path(__file__).resolve().parent.parent / "app" / "schema.sql").read_text()
    cols = ", ".join(COLUMNS)
    marks = ", ".join("%s" for _ in COLUMNS)

    src = sqlite3.connect(src_path)
    migrate_sqlite(src)
    with psycopg.connect(dsn, options=f"-c search_path={schema}") as dst:
        dst.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
        dst.execute(ddl)
        migrate_pg(dst, schema)
        (n,) = dst.execute("SELECT count(*) FROM entries").fetchone()
        if n:
            sys.exit(f"refusing to run: entries already has {n} rows in Postgres")
        rows = src.execute(f"SELECT {cols} FROM entries").fetchall()
        with dst.cursor() as cur:
            cur.executemany(f"INSERT INTO entries({cols}) VALUES({marks})", rows)
        print(f"copied {len(rows)} rows into schema {schema}")


if __name__ == "__main__":
    main()
