import time
import uuid

# Synthetic (depression, adhd) scores per day, oldest first.
ROWS = [
    (68, 62), (60, 61), (77, 54), (88, 65), (89, 79), (87, 82), (86, 64),
    (89, 82), (83, 65), (79, 63), (80, 56), (65, 64), (83, 66), (76, 78),
    (89, 66), (81, 77), (89, 71), (76, 69), (81, 71),
]


def seed_if_empty(store) -> int:
    """Insert ROWS on consecutive days ending today. No-op if the table has rows."""
    if store.list_entries(0):
        return 0
    now = int(time.time())
    for i, (dep, adhd) in enumerate(ROWS):
        day = len(ROWS) - 1 - i
        store.insert_entry(dict(
            id=uuid.uuid4().hex, created_at=now - day * 86400, depression=dep, adhd=adhd, note="",
        ))
    return len(ROWS)
