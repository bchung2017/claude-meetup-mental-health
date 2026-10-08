"""Load CareLinq-format patient bundles into the integrated schema (docs/integrated-patient-schema.md).

A bundle directory holds patient.json, self_report.json, healthkit.json and optionally
behavidence.json (daily MHSS). Rows are produced in schema file order, which is valid FK order.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from .stores.base import TABLES

PATIENTS_DIR = Path(__file__).resolve().parent.parent / "data" / "patients"

HK_METRICS = (
    "HKQuantityTypeIdentifierStepCount", "HKQuantityTypeIdentifierActiveEnergyBurned",
    "HKQuantityTypeIdentifierAppleExerciseTime", "HKQuantityTypeIdentifierRestingHeartRate",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN", "HKQuantityTypeIdentifierRespiratoryRate",
    "HKQuantityTypeIdentifierTimeInDaylight", "HKCategoryTypeIdentifierMindfulSession",
)
MHSS_METRICS = {"anxiety": "BHVD_MHSS_ANXIETY", "stress": "BHVD_MHSS_STRESS",
                "depression": "BHVD_MHSS_DEPRESSION", "adhd": "BHVD_MHSS_ADHD"}
INSTRUMENT_MAX = {"PHQ-9": 27, "GAD-7": 21}


def _split_name(full: str) -> tuple[str, str | None]:
    name, _, cred = full.partition(",")
    return name.strip(), (cred.strip() or None)


def bundle_to_rows(patient: dict, self_report: dict, healthkit: dict, behavidence: dict | None,
                   origin: str) -> dict[str, list[dict]]:
    pid = patient["patient_id"]
    if self_report["patient_id"] != pid or healthkit["patient_id"] != pid:
        raise ValueError("patient_id mismatch across bundle files")
    enr = patient["enrollment"]
    win = enr["observation_window"]
    src = f"src_carelinq_{pid}"
    src_bhvd = f"src_behavidence_{pid}"
    synthetic = int(bool(patient.get("_synthetic")))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: dict[str, list[dict]] = {t: [] for t in TABLES}
    add = lambda t, r: rows[t].append(r)  # noqa: E731

    add("data_sources", dict(source_id=src, kind="json_bundle", label=f"CareLinq bundle {pid}", origin_uri=origin,
                             content_sha256=None, ingested_at=now, period_start=win["start"], period_end=win["end"],
                             is_synthetic=synthetic, is_deidentified=0, authority_rank=100))
    if behavidence:
        add("data_sources", dict(source_id=src_bhvd, kind="device_sync", label=f"Behavidence MHSS {pid}",
                                 origin_uri=origin, content_sha256=None, ingested_at=now,
                                 period_start=win["start"], period_end=win["end"],
                                 is_synthetic=int(bool(behavidence.get("_synthetic"))), is_deidentified=0, authority_rank=200))

    add("patients", dict(patient_id=pid, display_name=patient.get("display_name"), date_of_birth=patient.get("date_of_birth"),
                         sex_at_birth=patient.get("sex_at_birth"), pronouns=patient.get("pronouns"),
                         timezone=patient["timezone"], is_synthetic=synthetic, created_at=enr["enrolled_at"]))
    add("patient_identifiers", dict(patient_id=pid, source_id=src, id_type="internal", id_value=pid))
    add("enrollments", dict(patient_id=pid, program=enr["program"], source_id=src, enrolled_at=enr["enrolled_at"],
                            window_start=win["start"], window_end=win["end"], practices_start=enr.get("practices_start")))
    consents = enr.get("consents", {})
    for scope in ("self_report_sharing", "healthkit_sharing", "journal_ai_summary", "voice_note_transcription"):
        if scope in consents:
            add("consents", dict(patient_id=pid, scope=scope, granted=int(bool(consents[scope])),
                                 granted_at=enr["enrolled_at"], revoked_at=None, source_id=src))
    for hk in consents.get("healthkit_types_authorized", []):
        add("consents", dict(patient_id=pid, scope=f"hk_type:{hk}", granted=1, granted_at=enr["enrolled_at"],
                             revoked_at=None, source_id=src))
    if behavidence:
        add("consents", dict(patient_id=pid, scope="passive_mobile_monitoring", granted=1,
                             granted_at=enr["enrolled_at"], revoked_at=None, source_id=src_bhvd))
    for dev in enr.get("devices", []):
        add("devices", dict(patient_id=pid, device_type=dev["type"], model=dev.get("model"), os_version=dev.get("os"), source_id=src))

    clin = patient.get("clinical", {})
    dxs = ([clin["primary_diagnosis"]] if clin.get("primary_diagnosis") else []) + list(clin.get("secondary_diagnoses", []))
    for n, dx in enumerate(dxs):
        add("diagnoses", dict(diagnosis_id=f"dx_{pid}_{n}", patient_id=pid, icd10=dx["icd10"], description=dx["description"],
                              rank="primary" if n == 0 else "secondary", category="psychiatric",
                              asserted_on=win["start"], source_id=src))
    for n, med in enumerate(clin.get("medications", [])):
        add("medications", dict(medication_id=f"med_{pid}_{n}", patient_id=pid, name=med["name"], dose=med.get("dose"),
                                route="oral", frequency=med.get("frequency"), started_on=med.get("started"), ended_on=None,
                                status="active", is_monitored=0, notes=None, source_id=src))
    therapist = None
    for c in patient.get("care_team", []):
        name, cred = _split_name(c["name"])
        if c["role"] == "primary_therapist":
            therapist = c["clinician_id"]
        add("care_team", dict(patient_id=pid, clinician_id=c["clinician_id"], name=name, credential=cred,
                              role=c["role"], organization=None, source_id=src))

    for s in patient.get("sessions", []):
        add("encounters", dict(encounter_id=f"{pid}_{s['session_id']}", patient_id=pid,
                               encounter_type="intake" if s.get("cpt_code") == "90791" else
                               "therapy_session" if dxs else "check_in",
                               sequence_number=s.get("session_number"), scheduled_start=s["scheduled_start"],
                               duration_min=s.get("duration_min"), modality=s.get("modality"), cpt_code=s.get("cpt_code"),
                               attended=int(bool(s.get("attended"))), clinician_id=therapist, source_id=src))

    journals = self_report.get("journal_entries", [])
    events = list(patient.get("clinical_events") or [])
    if not events:  # derive the two cross-source events Maya's bundle implies from journal themes
        for e in journals:
            if "job_loss" in e["ai_themes"] and not any(x["label"] == "job_loss" for x in events):
                events.append(dict(category="psychosocial_stressor", label="job_loss", description=e["ai_summary"],
                                   onset_at=e["created_at"], resolved_at=None, valence=-1, evidence_ref=e["entry_id"]))
            if "safety_planning" in e["ai_themes"]:
                events.append(dict(category="safety", label="safety_plan_created", description=e["ai_summary"],
                                   onset_at=e["created_at"], resolved_at=None, valence=1, evidence_ref=e["entry_id"]))
            if "job_search" in e["ai_themes"] and "relief" in e["ai_themes"]:
                events.append(dict(category="milestone", label="job_offer", description=e["ai_summary"],
                                   onset_at=e["created_at"], resolved_at=None, valence=1, evidence_ref=e["entry_id"]))
    for n, ev in enumerate(events):
        add("clinical_events", dict(event_id=f"evt_{pid}_{n}", patient_id=pid, category=ev["category"], label=ev["label"],
                                    description=ev.get("description"), onset_at=ev["onset_at"], resolved_at=ev.get("resolved_at"),
                                    valence=ev.get("valence"), source_id=src, evidence_ref=ev.get("evidence_ref")))

    for key in ("phq9_responses", "gad7_responses"):
        for r in self_report.get(key, []):
            inst = r["instrument"]
            item9 = next((i["score"] for i in r["items"] if i["item"] == 9), None) if inst == "PHQ-9" else None
            add("assessments", dict(assessment_id=r["response_id"], patient_id=pid, instrument=inst,
                                    administered_at=r["completed_at"], administration_week=r.get("administration_week"),
                                    total_score=r["total_score"], max_score=INSTRUMENT_MAX[inst],
                                    severity_band=r.get("severity_band"), functional_difficulty=r.get("functional_difficulty"),
                                    phq9_item9_score=item9, context_note=None,
                                    is_baseline=int(r.get("administration_week") == 0), source_id=src))
            for i in r["items"]:
                add("assessment_items", dict(assessment_id=r["response_id"], item_number=i["item"], item_text=i["text"], score=i["score"]))

    for m in self_report.get("mood_checkins", []):
        add("mood_checkins", dict(checkin_id=m["checkin_id"], patient_id=pid, logged_at=m["logged_at"], mood=m["mood"],
                                  anxiety=m["anxiety"], energy=m["energy"], note=m.get("note"), source_id=src))
        for tag in m.get("emotion_tags", []):
            add("mood_checkin_tags", dict(checkin_id=m["checkin_id"], tag=tag))

    for e in journals:
        add("narratives", dict(narrative_id=e["entry_id"], patient_id=pid, medium="journal", created_at=e["created_at"],
                               body_text=e["text"], word_count=e.get("word_count"), duration_sec=None, audio_uri=None,
                               transcription_confidence=None, ai_summary=e.get("ai_summary"), sentiment_score=e.get("sentiment_score"),
                               shared_with_clinician=int(bool(e.get("shared_with_clinician"))), source_id=src))
        for t in e.get("ai_themes", []):
            add("narrative_themes", dict(narrative_id=e["entry_id"], theme=t))
        if "passive_ideation" in e.get("ai_themes", []):
            add("risk_assessments", dict(risk_id=f"risk_{e['entry_id']}", patient_id=pid, assessed_at=e["created_at"],
                                         encounter_id=None, ideation="passive", has_plan=0, has_intent=0, chronic_risk=None,
                                         finding=e.get("ai_summary"), significance="Risk language detected in journal text",
                                         detected_by="nlp_narrative", source_id=src))
        if "safety_planning" in e.get("ai_themes", []):
            add("safety_plans", dict(plan_id=f"plan_{e['entry_id']}", patient_id=pid, created_at=e["created_at"],
                                     created_with=therapist, escalation_note=e.get("ai_summary"), source_id=src))
    for v in self_report.get("voice_notes", []):
        add("narratives", dict(narrative_id=v["voice_note_id"], patient_id=pid, medium="voice_note", created_at=v["recorded_at"],
                               body_text=v.get("transcript"), word_count=None, duration_sec=v.get("duration_sec"),
                               audio_uri=v.get("audio_uri"), transcription_confidence=v.get("transcription_confidence"),
                               ai_summary=v.get("ai_summary"), sentiment_score=v.get("sentiment_score"),
                               shared_with_clinician=int(bool(v.get("shared_with_clinician"))), source_id=src))

    pr = self_report.get("practices", {})
    for p in pr.get("definitions", []):
        add("practices", dict(patient_id=pid, practice_id=p["practice_id"], name=p["name"], track=p["track"],
                              target_per_week=p.get("target_per_week"), trigger_text=p.get("trigger"),
                              created_at=p["created_at"], source_id=src))
    for l in pr.get("daily_logs", []):
        add("practice_daily_logs", dict(log_id=l["log_id"], patient_id=pid, practice_id=l["practice_id"],
                                        log_date=l["date"], completed=int(bool(l["completed"]))))
    for c in pr.get("weekly_cycles", []):
        add("practice_weekly_cycles", dict(patient_id=pid, practice_id=c["practice_id"], week=c["week"],
                                           cycle_start=c["cycle_start"], cycle_end=c["cycle_end"], target=c["target"],
                                           completed=c["completed"], met_target=int(bool(c["met_target"]))))
    for l in pr.get("meet_the_moment_logs", []):
        add("meet_the_moment_logs", dict(log_id=l["log_id"], patient_id=pid, practice_id=l["practice_id"],
                                         logged_at=l["logged_at"], situation=l.get("situation"), emotion_named=l.get("emotion_named"),
                                         intensity_before=l.get("intensity_before"), intensity_after=l.get("intensity_after")))

    sleep_nights = {s["night_of"] for s in healthkit.get("sleep_sessions", [])}
    mhss_days = {}
    if behavidence:
        for r in behavidence.get("daily", []):
            mhss_days[r["date"]] = r
            for k, code in MHSS_METRICS.items():
                add("daily_observations", dict(patient_id=pid, obs_date=r["date"], metric_code=code,
                                               value=r.get(k), source_id=src_bhvd))
    for dm in healthkit.get("daily_metrics", []):
        for code in HK_METRICS:
            add("daily_observations", dict(patient_id=pid, obs_date=dm["date"], metric_code=code,
                                           value=dm[code]["value"], source_id=src))
        add("observation_coverage", dict(patient_id=pid, obs_date=dm["date"], watch_worn=int(bool(dm["watch_worn"])),
                                         phone_monitoring=int(dm["date"] in mhss_days) if behavidence else None,
                                         sleep_session_present=int(dm["date"] in sleep_nights)))
    for s in healthkit.get("sleep_sessions", []):
        st = s.get("stages_min", {})
        add("sleep_sessions", dict(patient_id=pid, night_of=s["night_of"], device_source=s.get("source"),
                                   in_bed_start=s["in_bed_start"], in_bed_end=s["in_bed_end"],
                                   sleep_onset_latency_min=s.get("sleep_onset_latency_min"), total_asleep_min=s.get("total_asleep_min"),
                                   awake_min=s.get("awake_min"), awakenings=s.get("awakenings"),
                                   asleep_core_min=st.get("asleepCore"), asleep_deep_min=st.get("asleepDeep"),
                                   asleep_rem_min=st.get("asleepREM"), sleep_efficiency=s.get("sleep_efficiency"), source_id=src))

    if behavidence:
        days = len(mhss_days)
        add("rtm_periods", dict(rtm_period_id=f"rtm_{pid}_0", patient_id=pid, period_start=win["start"], period_end=win["end"],
                                monitoring_days=days, threshold_days=16, threshold_met=int(days >= 16), review_minutes=0,
                                assessments_sent=0, candidate_cpt="98980", eligibility_asserted=None,
                                eligibility_note="Monitoring days from device stream; no review time recorded.", source_id=src_bhvd))
    return rows


def load_bundle(directory: Path) -> dict[str, list[dict]]:
    read = lambda name: json.loads((directory / name).read_text())  # noqa: E731
    bhvd = read("behavidence.json") if (directory / "behavidence.json").exists() else None
    return bundle_to_rows(read("patient.json"), read("self_report.json"), read("healthkit.json"), bhvd, str(directory))


def import_bundle(store, directory: Path) -> dict[str, int]:
    rows = load_bundle(directory)
    for table in TABLES:
        store.insert_rows(table, rows[table])
    return {t: len(r) for t, r in rows.items() if r}


def bundle_dirs(root: Path = PATIENTS_DIR) -> list[Path]:
    return sorted(p for p in root.iterdir() if (p / "patient.json").exists())


def import_all(store, root: Path = PATIENTS_DIR) -> dict[str, dict[str, int]]:
    return {p.name: import_bundle(store, p) for p in bundle_dirs(root)}


def seed_patients_if_empty(store) -> dict | None:
    if store.list_rows("patients"):
        return None
    return import_all(store)
