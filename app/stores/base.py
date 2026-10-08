from abc import ABC, abstractmethod

METRICS = ("depression", "adhd")
COLUMNS = ("id", "created_at", *METRICS, "meds_taken", "note")

# Columns added after the initial schema; applied idempotently on startup.
ADDED_COLUMNS = (("meds_taken", "INTEGER NOT NULL DEFAULT 0"),)


class Store(ABC):
    backend: str

    @abstractmethod
    def insert_entry(self, row: dict) -> None: ...

    @abstractmethod
    def list_entries(self, since: int) -> list[dict]: ...

    @abstractmethod
    def delete_entry(self, id: str) -> int: ...
