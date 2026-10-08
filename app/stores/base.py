from abc import ABC, abstractmethod

METRICS = ("depression", "adhd")
COLUMNS = ("id", "created_at", *METRICS, "note")


class Store(ABC):
    backend: str

    @abstractmethod
    def insert_entry(self, row: dict) -> None: ...

    @abstractmethod
    def list_entries(self, since: int) -> list[dict]: ...

    @abstractmethod
    def delete_entry(self, id: str) -> int: ...
