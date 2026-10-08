import time
import uuid

# Synthetic (depression, adhd, adherence) scores per day, oldest first.
ROWS = [
    (68, 62, 100), (60, 61, 100), (77, 54, 40), (88, 65, 0), (89, 79, 20),
    (87, 82, 85), (86, 64, 100), (89, 82, 55), (83, 65, 100), (79, 63, 90),
    (80, 56, 100), (65, 64, 100), (83, 66, 30), (76, 78, 75), (89, 66, 50),
    (81, 77, 100), (89, 71, 25), (76, 69, 80), (81, 71, 100),
]


def seed_if_empty(store) -> int:
    """Insert ROWS on consecutive days ending today. No-op if the table has rows."""
    if store.list_entries(0):
        return 0
    now = int(time.time())
    for i, (dep, adhd, adherence) in enumerate(ROWS):
        day = len(ROWS) - 1 - i
        store.insert_entry(dict(
            id=uuid.uuid4().hex, created_at=now - day * 86400,
            depression=dep, adhd=adhd, adherence=adherence, note="",
        ))
    return len(ROWS)
