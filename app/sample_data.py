import time
import uuid

# Synthetic (depression, adhd, meds_taken) per day, oldest first.
ROWS = [
    (68, 62, True), (60, 61, True), (77, 54, False), (88, 65, False), (89, 79, False),
    (87, 82, True), (86, 64, True), (89, 82, False), (83, 65, True), (79, 63, True),
    (80, 56, True), (65, 64, True), (83, 66, False), (76, 78, True), (89, 66, False),
    (81, 77, True), (89, 71, False), (76, 69, True), (81, 71, True),
]


def seed_if_empty(store) -> int:
    """Insert ROWS on consecutive days ending today. No-op if the table has rows."""
    if store.list_entries(0):
        return 0
    now = int(time.time())
    for i, (dep, adhd, meds) in enumerate(ROWS):
        day = len(ROWS) - 1 - i
        store.insert_entry(dict(
            id=uuid.uuid4().hex, created_at=now - day * 86400,
            depression=dep, adhd=adhd, meds_taken=int(meds), note="",
        ))
    return len(ROWS)
