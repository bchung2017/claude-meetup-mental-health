"""Import the CareLinq per-patient JSON bundle (patient.json, self_report.json, healthkit.json).

Field mapping follows data/sample/README.md. Nested objects are stored as JSON text;
HealthKit daily metrics are flattened to one column per identifier.
"""
import json
from pathlib import Path

from .stores.base import JSON_COLUMNS, PATIENT_TABLES

HK_COLUMNS = {
    "HKQuantityTypeIdentifierStepCount": "step_count",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_energy_kcal",
    "HKQuantityTypeIdentifierAppleExerciseTime": "exercise_min",
    "HKQuantityTypeIdentifierRestingHeartRate": "resting_hr",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv_sdnn_ms",
    "HKQuantityTypeIdentifierRespiratoryRate": "respiratory_rate",
    "HKQuantityTypeIdentifierTimeInDaylight": "time_in_daylight_min",
    "HKCategoryTypeIdentifierMindfulSession": "mindful_min",
}


def _j(v):
    return json.dumps(v, ensure_ascii=False)


def bundle_to_rows(patient: dict, self_report: dict, healthkit: dict) -> dict[str, list[dict]]:
    pid = patient["patient_id"]
    if self_report["patient_id"] != pid or healthkit["patient_id"] != pid:
        raise ValueError("patient_id mismatch across bundle files")
    with_pid = lambda rows: [{**r, "patient_id": pid} for r in rows]  # noqa: E731
    pr = self_report["practices"]

    return {
        "patients": [{
            **{k: patient[k] for k in ("patient_id", "display_name", "date_of_birth", "sex_at_birth", "pronouns", "timezone")},
            "enrollment": _j(patient["enrollment"]),
            "clinical": _j(patient["clinical"]),
            "care_team": _j(patient["care_team"]),
        }],
        "sessions": with_pid([{**s, "attended": int(s["attended"])} for s in patient["sessions"]]),
        "phq9_responses": with_pid([
            {**r, "items": _j(r["items"]), "item9_score": next(i["score"] for i in r["items"] if i["item"] == 9)}
            for r in self_report["phq9_responses"]
        ]),
        "mood_checkins": with_pid([{**m, "emotion_tags": _j(m["emotion_tags"])} for m in self_report["mood_checkins"]]),
        "journal_entries": with_pid([
            {**e, "ai_themes": _j(e["ai_themes"]), "shared_with_clinician": int(e["shared_with_clinician"])}
            for e in self_report["journal_entries"]
        ]),
        "voice_notes": with_pid([
            {**v, "shared_with_clinician": int(v["shared_with_clinician"])} for v in self_report["voice_notes"]
        ]),
        "practices": with_pid([{**p, "trigger_text": p.get("trigger")} for p in pr["definitions"]]),
        "practice_daily_logs": with_pid([{**l, "completed": int(l["completed"])} for l in pr["daily_logs"]]),
        "practice_weekly_cycles": with_pid([{**c, "met_target": int(c["met_target"])} for c in pr["weekly_cycles"]]),
        "meet_the_moment_logs": with_pid(pr["meet_the_moment_logs"]),
        "sleep_sessions": with_pid([
            {
                **s,
                "asleep_core_min": s["stages_min"]["asleepCore"],
                "asleep_deep_min": s["stages_min"]["asleepDeep"],
                "asleep_rem_min": s["stages_min"]["asleepREM"],
            }
            for s in healthkit["sleep_sessions"]
        ]),
        "daily_metrics": with_pid([
            {
                "date": d["date"],
                "watch_worn": int(d["watch_worn"]),
                **{col: d[hk]["value"] for hk, col in HK_COLUMNS.items()},
            }
            for d in healthkit["daily_metrics"]
        ]),
    }


def import_bundle(store, directory: Path) -> dict[str, int]:
    load = lambda name: json.loads((directory / name).read_text())  # noqa: E731
    rows = bundle_to_rows(load("patient.json"), load("self_report.json"), load("healthkit.json"))
    for table in PATIENT_TABLES:  # schema order: patients first
        store.insert_rows(table, rows[table])
    return {t: len(r) for t, r in rows.items()}


def decode_row(table: str, row: dict) -> dict:
    for col in JSON_COLUMNS.get(table, ()):
        row[col] = json.loads(row[col])
    return row


SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"


def seed_sample_if_empty(store) -> dict[str, int] | None:
    if store.list_rows("patients"):
        return None
    return import_bundle(store, SAMPLE_DIR)
