from abc import ABC, abstractmethod

METRICS = ("depression", "adhd")
COLUMNS = ("id", "created_at", *METRICS, "meds_taken", "note")

# Columns added after the initial schema; applied idempotently on startup.
ADDED_COLUMNS = (("meds_taken", "INTEGER NOT NULL DEFAULT 0"),)

# Per-patient tables: name -> (columns, order-by column). Every table carries patient_id.
PATIENT_TABLES = {
    "patients": (
        ("patient_id", "display_name", "date_of_birth", "sex_at_birth", "pronouns", "timezone",
         "enrollment", "clinical", "care_team"),
        "patient_id",
    ),
    "sessions": (
        ("session_id", "patient_id", "session_number", "scheduled_start", "duration_min",
         "modality", "cpt_code", "attended"),
        "scheduled_start",
    ),
    "phq9_responses": (
        ("response_id", "patient_id", "administration_week", "completed_at", "items",
         "total_score", "item9_score", "severity_band", "functional_difficulty"),
        "completed_at",
    ),
    "mood_checkins": (
        ("checkin_id", "patient_id", "logged_at", "mood", "anxiety", "energy", "emotion_tags", "note"),
        "logged_at",
    ),
    "journal_entries": (
        ("entry_id", "patient_id", "created_at", "text", "word_count", "ai_summary", "ai_themes",
         "sentiment_score", "shared_with_clinician"),
        "created_at",
    ),
    "voice_notes": (
        ("voice_note_id", "patient_id", "recorded_at", "duration_sec", "audio_uri", "transcript",
         "transcription_confidence", "ai_summary", "sentiment_score", "shared_with_clinician"),
        "recorded_at",
    ),
    "practices": (
        ("patient_id", "practice_id", "name", "track", "target_per_week", "trigger_text", "created_at"),
        "created_at",
    ),
    "practice_daily_logs": (
        ("log_id", "patient_id", "practice_id", "date", "completed"),
        "date",
    ),
    "practice_weekly_cycles": (
        ("patient_id", "practice_id", "week", "cycle_start", "cycle_end", "target", "completed", "met_target"),
        "week",
    ),
    "meet_the_moment_logs": (
        ("log_id", "patient_id", "practice_id", "logged_at", "situation", "emotion_named",
         "intensity_before", "intensity_after"),
        "logged_at",
    ),
    "sleep_sessions": (
        ("patient_id", "night_of", "source", "in_bed_start", "in_bed_end", "sleep_onset_latency_min",
         "total_asleep_min", "awake_min", "awakenings", "asleep_core_min", "asleep_deep_min",
         "asleep_rem_min", "sleep_efficiency"),
        "night_of",
    ),
    "daily_metrics": (
        ("patient_id", "date", "watch_worn", "step_count", "active_energy_kcal", "exercise_min",
         "resting_hr", "hrv_sdnn_ms", "respiratory_rate", "time_in_daylight_min", "mindful_min"),
        "date",
    ),
}

# JSON-text columns, decoded on read.
JSON_COLUMNS = {
    "patients": ("enrollment", "clinical", "care_team"),
    "phq9_responses": ("items",),
    "mood_checkins": ("emotion_tags",),
    "journal_entries": ("ai_themes",),
}


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
        """Bulk insert into a PATIENT_TABLES table; existing primary keys are skipped."""

    @abstractmethod
    def list_rows(self, table: str, patient_id: str | None = None) -> list[dict]:
        """Rows of a PATIENT_TABLES table, optionally for one patient, in table order."""


def table_spec(table: str) -> tuple[tuple[str, ...], str]:
    if table not in PATIENT_TABLES:
        raise KeyError(f"unknown table {table!r}")
    return PATIENT_TABLES[table]
