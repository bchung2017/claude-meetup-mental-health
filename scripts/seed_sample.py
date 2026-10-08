"""Seed synthetic sample rows. Usage: python scripts/seed_sample.py [--replace]
Honors DATABASE_URL / SQLITE_PATH. Refuses to run on a non-empty table unless --replace,
which deletes every existing entry first."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.sample_data import seed, seed_if_empty  # noqa: E402
from app.stores import get_store  # noqa: E402

if __name__ == "__main__":
    store = get_store()
    if "--replace" in sys.argv[1:]:
        for e in store.list_entries(0):
            store.delete_entry(e["id"])
        n = seed(store)
    else:
        n = seed_if_empty(store)
    print(f"seeded {n} entries into {store.backend}" if n else "table not empty, nothing seeded (use --replace)")
