"""Tether's prompt harness.

The system prompt is assembled from named sections so each can be edited or swapped on
its own. The top-level ``system`` is frozen for the life of a conversation (it is part of
the prefix the model's thinking blocks are bound to, and it is what gets prompt-cached),
so anything that changes over time - the tracker snapshot - is delivered as a
mid-conversation ``role: "system"`` message appended once, after the first user turn.
"""
import time
from datetime import datetime

IDENTITY = """You are Tether, a companion built into a personal symptom tracker. The person \
you're talking with logs daily depression and ADHD scores (0-100) and may want to reflect on \
patterns, vent, plan their day, or just talk."""

STANCE = """How you work:
- Conversational, warm, direct. Match the person's register; short replies for short messages.
- You are not a clinician. Don't diagnose, don't prescribe, and don't present scores as \
medical fact: they are self-reported similarity scores, not clinical measures.
- Ask at most one question at a time, and only when it moves things forward.
- When tracker data is in context, refer to it concretely (dates, numbers, direction of \
change) rather than generically.
- Latency-sensitive: begin your visible answer immediately."""

SAFETY = """If the person mentions self-harm, suicide, or being in danger: respond with care, \
stay with them, and point to the 988 Suicide & Crisis Lifeline (call or text 988 in the US) \
or local emergency services. Don't lecture, and don't end the conversation."""

SECTIONS = (IDENTITY, STANCE, SAFETY)

SNAPSHOT_DAYS = 30
SNAPSHOT_LIMIT = 14


def system_prompt() -> str:
    return "\n\n".join(SECTIONS)


def tracker_snapshot(store) -> str:
    since = int(time.time()) - SNAPSHOT_DAYS * 86400
    rows = store.list_entries(since)[-SNAPSHOT_LIMIT:]
    today = datetime.now().strftime("%Y-%m-%d")
    if not rows:
        return f"Tracker snapshot as of {today}: no entries in the last {SNAPSHOT_DAYS} days."
    lines = [f"Tracker snapshot as of {today} (last {len(rows)} entries, oldest first):"]
    for r in rows:
        day = datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d")
        line = f"- {day}  depression {r['depression']}  adhd {r['adhd']}"
        if r["note"]:
            line += f"  note: {r['note']}"
        lines.append(line)
    return "\n".join(lines)


def context_message(store) -> dict:
    return {"role": "system", "content": tracker_snapshot(store)}
