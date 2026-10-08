"""Tether's prompt harness.

The meta prompt lives in a file (default ``prompts/clinician.md``, override with
``TETHER_PROMPT_FILE``) and is read once at startup. It becomes the top-level ``system``,
which is frozen for the life of a conversation: it is part of the prefix the model's
thinking blocks are bound to, and it is what gets prompt-cached.

Anything that changes over time - the patient record - is delivered instead as a
mid-conversation ``role: "system"`` message appended once, after the first user turn.
"""
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from ..carelinq import decode_row
from ..config import Config
from ..stores.base import PATIENT_TABLES

DEFAULT_PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "clinician.md"

# practice_daily_logs is omitted: practice_weekly_cycles is its rollup.
STREAMS = tuple(t for t in PATIENT_TABLES if t not in ("patients", "practice_daily_logs"))
SKIP_COLUMNS = {"patient_id", "audio_uri"}


@lru_cache(maxsize=1)
def system_prompt() -> str:
    path = Path(Config.TETHER_PROMPT_FILE) if Config.TETHER_PROMPT_FILE else DEFAULT_PROMPT_FILE
    return path.read_text().strip()


def _line(row: dict) -> str:
    parts = []
    for k, v in row.items():
        if k in SKIP_COLUMNS or v is None or k.endswith("_id"):
            continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        parts.append(f"{k}={v}")
    return "- " + "  ".join(parts)


def _patient(store):
    rows = store.list_rows("patients", Config.TETHER_PATIENT_ID) if Config.TETHER_PATIENT_ID else store.list_rows("patients")
    return decode_row("patients", rows[0]) if rows else None


def patient_record(store) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    out = [f"Patient record as of {today}."]
    patient = _patient(store)
    if patient is None:
        out.append("No patient on file.")
    else:
        pid = patient["patient_id"]
        out.append(f"## patient\n{_line(patient)}")
        for table in STREAMS:
            rows = [decode_row(table, r) for r in store.list_rows(table, pid)]
            out.append(f"## {table} ({len(rows)} rows)\n" + "\n".join(_line(r) for r in rows))

    entries = store.list_entries(0)
    out.append(f"## behavidence_scores ({len(entries)} rows; depression/adhd are 0-100 similarity scores)")
    for r in entries:
        day = datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d")
        meds = "taken" if r["meds_taken"] else "missed"
        line = f"- date={day}  depression={r['depression']}  adhd={r['adhd']}  meds={meds}"
        if r["note"]:
            line += f"  note={r['note']}"
        out.append(line)
    return "\n\n".join(out)


def context_message(store) -> dict:
    return {"role": "system", "content": patient_record(store)}


def patient_label(store) -> str | None:
    p = _patient(store)
    return p["display_name"] if p else None
