import time
import uuid

# Synthetic (depression, adhd, adherence) scores per day, oldest first.
# Adherence is spiky on purpose: with one or two meds a day it lands on 0, 50 or 100, not a smooth curve.
ROWS = [
    (68, 62, 100), (60, 61, 100), (77, 54, 0), (88, 65, 0), (89, 79, 50),
    (87, 82, 100), (86, 64, 100), (89, 82, 0), (83, 65, 100), (79, 63, 100),
    (80, 56, 50), (65, 64, 100), (83, 66, 0), (76, 78, 100), (89, 66, 0),
    (81, 77, 100), (89, 71, 0), (76, 69, 50), (81, 71, 100),
]


def seed_if_empty(store) -> int:
    """Insert ROWS on consecutive days ending today. No-op if the table has rows."""
    if store.list_entries(0):
        return 0
    return seed(store)


def seed(store) -> int:
    now = int(time.time())
    for i, (dep, adhd, adherence) in enumerate(ROWS):
        day = len(ROWS) - 1 - i
        store.insert_entry(dict(
            id=uuid.uuid4().hex, created_at=now - day * 86400,
            depression=dep, adhd=adhd, adherence=adherence, note="",
        ))
    return len(ROWS)
