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
