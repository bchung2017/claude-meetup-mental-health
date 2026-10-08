import re
from abc import ABC, abstractmethod
from pathlib import Path

METRICS = ("depression", "adhd", "adherence")
COLUMNS = ("id", "created_at", *METRICS, "note")

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"
_DDL = SCHEMA_PATH.read_text()

# Per-patient model: every table and view in schema.sql except the tracker's `entries`.
# Order follows the file, which is also valid FK insert order.
TABLES = tuple(t for t in re.findall(r"^CREATE TABLE IF NOT EXISTS (\w+)", _DDL, re.M) if t != "entries")
VIEWS = tuple(re.findall(r"^CREATE VIEW (\w+) AS", _DDL, re.M))
RELATIONS = frozenset(TABLES + VIEWS)

# Reference tables carry no patient_id.
REFERENCE_TABLES = frozenset({"data_sources", "metric_definitions", "theme_definitions"})
# assessment_items / *_tags / *_themes hang off a parent row, not a patient.
CHILD_TABLES = frozenset({"assessment_items", "mood_checkin_tags", "narrative_themes"})

# Default ORDER BY per relation; anything not listed is unordered.
ORDER_BY = {
    "encounters": "scheduled_start", "clinical_events": "onset_at", "assessments": "administered_at",
    "assessment_items": "assessment_id, item_number", "mood_checkins": "logged_at",
    "narratives": "created_at", "practices": "created_at", "practice_daily_logs": "log_date",
    "practice_weekly_cycles": "practice_id, week", "meet_the_moment_logs": "logged_at",
    "daily_observations": "obs_date, metric_code", "observation_coverage": "obs_date",
    "sleep_sessions": "night_of", "risk_assessments": "assessed_at", "rtm_periods": "period_start",
    "rtm_activities": "occurred_at", "care_plan_items": "recorded_at", "source_conflicts": "conflict_id",
    "v_healthkit_daily": "obs_date", "v_mhss_daily": "obs_date", "v_daily_integrated": "obs_date",
    "v_safety_signals": "priority, signal_at", "patients": "display_name",
}

# Tables of the previous (12-table) per-patient model. Dropped once when found without `data_sources`.
LEGACY_TABLES = (
    "daily_metrics", "sleep_sessions", "meet_the_moment_logs", "practice_weekly_cycles",
    "practice_daily_logs", "practices", "voice_notes", "journal_entries", "mood_checkins",
    "phq9_responses", "sessions", "patients",
)


def check_relation(name: str) -> str:
    if name not in RELATIONS:
        raise KeyError(f"unknown relation {name!r}")
    return name


class Store(ABC):
    backend: str

    @abstractmethod
    def insert_entry(self, row: dict) -> None: ...

    @abstractmethod
    def list_entries(self, since: int) -> list[dict]: ...

    @abstractmethod
    def delete_entry(self, id: str) -> int: ...

    @abstractmethod
    def insert_rows(self, table: str, rows: list[dict]) -> None:
        """Bulk insert; rows sharing a primary/unique key with an existing row are skipped."""

    @abstractmethod
    def list_rows(self, table: str, patient_id: str | None = None) -> list[dict]:
        """All rows of a table or view, optionally scoped to one patient, in ORDER_BY order."""

    @abstractmethod
    def delete_patient_rows(self, patient_id: str) -> None:
        """Remove every row belonging to one patient (child rows first)."""
