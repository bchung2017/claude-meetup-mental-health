"""Seed the 19 daily depression/ADHD MHSS rows from the sample Behavidence report.

Dates in the source are redacted; rows are placed on consecutive days ending today.
Usage: python scripts/seed_sample.py   (honors DATABASE_URL / SQLITE_PATH like the app)
"""
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.stores import get_store  # noqa: E402

# (depression, adhd) per monitoring day, in order.
ROWS = [
    (68, 62), (60, 61), (77, 54), (88, 65), (89, 79), (87, 82), (86, 64),
    (89, 82), (83, 65), (79, 63), (80, 56), (65, 64), (83, 66), (76, 78),
    (89, 66), (81, 77), (89, 71), (76, 69), (81, 71),
]


def main() -> None:
    store = get_store()
    if store.list_entries(0):
        sys.exit("refusing to seed: entries table is not empty")
    now = int(time.time())
    for i, (dep, adhd) in enumerate(ROWS):
        day = len(ROWS) - 1 - i
        store.insert_entry(dict(
            id=uuid.uuid4().hex, created_at=now - day * 86400, depression=dep, adhd=adhd, note="",
        ))
    print(f"seeded {len(ROWS)} entries into {store.backend}")


if __name__ == "__main__":
    main()
