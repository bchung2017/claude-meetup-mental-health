"""Seed synthetic sample rows. Usage: python scripts/seed_sample.py [--replace]
Honors DATABASE_URL / SQLITE_PATH. Refuses to run on a non-empty table unless --replace,
which deletes every existing entry first."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.sample_data import reseed, seed_if_empty  # noqa: E402
from app.stores import get_store  # noqa: E402

if __name__ == "__main__":
    store = get_store()
    n = reseed(store) if "--replace" in sys.argv[1:] else seed_if_empty(store)
    print(f"seeded {n} entries into {store.backend}" if n else "table not empty, nothing seeded (use --replace)")
