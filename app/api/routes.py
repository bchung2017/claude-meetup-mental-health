import time
import uuid

from flask import Blueprint, jsonify, request

from ..stores import get_store
from ..stores.base import METRICS

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    return jsonify(ok=True, backend=get_store().backend)


def _public(row: dict) -> dict:
    return {**row, "meds_taken": bool(row["meds_taken"])}


@bp.get("/entries")
def list_entries():
    days = request.args.get("days", default=30, type=int)
    since = 0 if days <= 0 else int(time.time()) - days * 86400
    return jsonify(entries=[_public(r) for r in get_store().list_entries(since)])


@bp.post("/entries")
def create_entry():
    body = request.get_json(silent=True) or {}
    row = dict(id=uuid.uuid4().hex, created_at=int(time.time()))
    for m in METRICS:
        try:
            v = int(body.get(m))
        except (TypeError, ValueError):
            return jsonify(error=f"{m} must be an integer 0-100"), 400
        if not 0 <= v <= 100:
            return jsonify(error=f"{m} must be an integer 0-100"), 400
        row[m] = v
    meds = body.get("meds_taken", False)
    if not isinstance(meds, bool):
        return jsonify(error="meds_taken must be a boolean"), 400
    row["meds_taken"] = int(meds)
    row["note"] = str(body.get("note") or "")[:280]
    get_store().insert_entry(row)
    return jsonify(_public(row)), 201


@bp.delete("/entries/<id>")
def delete_entry(id: str):
    n = get_store().delete_entry(id)
    return (jsonify(ok=True), 200) if n else (jsonify(error="not found"), 404)


# --- per-patient model (docs/integrated-patient-schema.md) ---

from ..stores.base import RELATIONS, REFERENCE_TABLES  # noqa: E402

PATIENT_RELATIONS = tuple(sorted(r for r in RELATIONS if r not in REFERENCE_TABLES and r != "patients"))


def _latest(rows, key):
    return max(rows, key=lambda r: r[key]) if rows else None


@bp.get("/patients")
def list_patients():
    store = get_store()
    patients = store.list_rows("patients")
    dx = store.list_rows("diagnoses")
    assess = [a for a in store.list_rows("assessments") if a["instrument"] == "PHQ-9"]
    signals = store.list_rows("v_safety_signals")
    conflicts = [c for c in store.list_rows("source_conflicts") if c["resolution"] == "unresolved"]
    out = []
    for p in patients:
        pid = p["patient_id"]
        latest = _latest([a for a in assess if a["patient_id"] == pid], "administered_at")
        out.append({
            **p,
            "diagnoses": [{"icd10": d["icd10"], "description": d["description"], "rank": d["rank"]}
                          for d in dx if d["patient_id"] == pid],
            "latest_phq9": latest and {"total_score": latest["total_score"], "severity_band": latest["severity_band"],
                                       "administered_at": latest["administered_at"]},
            "safety_signals": sum(1 for s in signals if s["patient_id"] == pid),
            "unresolved_conflicts": sum(1 for c in conflicts if c["patient_id"] == pid),
        })
    return jsonify(patients=out)


@bp.get("/patients/<patient_id>")
def get_patient(patient_id: str):
    rows = get_store().list_rows("patients", patient_id)
    if not rows:
        return jsonify(error="not found"), 404
    return jsonify(rows[0])


@bp.get("/patients/<patient_id>/dashboard")
def patient_dashboard(patient_id: str):
    store = get_store()
    rows = store.list_rows("patients", patient_id)
    if not rows:
        return jsonify(error="not found"), 404
    get = lambda rel: store.list_rows(rel, patient_id)  # noqa: E731
    return jsonify(
        patient=rows[0],
        enrollments=get("enrollments"), diagnoses=get("diagnoses"), medications=get("medications"),
        care_team=get("care_team"), encounters=get("encounters"), clinical_events=get("clinical_events"),
        assessments=get("assessments"), mood_checkins=get("mood_checkins"), narratives=get("narratives"),
        practices=get("practices"), practice_weekly_cycles=get("practice_weekly_cycles"),
        sleep_sessions=get("sleep_sessions"), healthkit_daily=get("v_healthkit_daily"), mhss_daily=get("v_mhss_daily"),
        safety_signals=get("v_safety_signals"), risk_assessments=get("risk_assessments"), safety_plans=get("safety_plans"),
        rtm_periods=get("rtm_periods"),
        source_conflicts=[c for c in get("source_conflicts") if c["resolution"] == "unresolved"],
    )


@bp.get("/patients/<patient_id>/<relation>")
def get_patient_relation(patient_id: str, relation: str):
    if relation not in PATIENT_RELATIONS:
        return jsonify(error=f"relation must be one of {', '.join(PATIENT_RELATIONS)}"), 404
    return jsonify({"patient_id": patient_id, relation: get_store().list_rows(relation, patient_id)})
