"""
Synthetic cohort generator. All people, names and events are fictional. Seeded.

Writes one CareLinq-format bundle per patient under data/patients/<patient_id>/:
patient.json, self_report.json, healthkit.json, behavidence.json. Maya (pt_7f3a9c21)
keeps her hand-authored bundle from data/patients/pt_7f3a9c21/generate.py; this script
only adds behavidence.json for her. Same 12-week window as Maya: Mon 2026-07-13 -> Sun 2026-10-04.

    python data/generate_cohort.py
"""
import json
import random
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "patients"
TZ = "-04:00"
START = date(2026, 7, 13)
DAYS = 84

PHQ9_ITEMS = [
    "Little interest or pleasure in doing things",
    "Feeling down, depressed, or hopeless",
    "Trouble falling or staying asleep, or sleeping too much",
    "Feeling tired or having little energy",
    "Poor appetite or overeating",
    "Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
    "Trouble concentrating on things, such as reading the newspaper or watching television",
    "Moving or speaking so slowly that other people could have noticed, or the opposite — being so fidgety or restless",
    "Thoughts that you would be better off dead, or of hurting yourself in some way",
]
GAD7_ITEMS = [
    "Feeling nervous, anxious, or on edge",
    "Not being able to stop or control worrying",
    "Worrying too much about different things",
    "Trouble relaxing",
    "Being so restless that it is hard to sit still",
    "Becoming easily annoyed or irritable",
    "Feeling afraid, as if something awful might happen",
]
EMO = {
    "low": ["hopeless", "numb", "drained", "ashamed", "lonely", "dread", "irritable", "overwhelmed"],
    "mid": ["restless", "flat", "uncertain", "tired", "wistful", "tense", "okay", "hopeful"],
    "high": ["content", "calm", "grateful", "energized", "proud", "connected", "relieved", "curious"],
}
HK_TYPES = [
    "HKCategoryTypeIdentifierSleepAnalysis", "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
    "HKQuantityTypeIdentifierRestingHeartRate", "HKQuantityTypeIdentifierStepCount",
    "HKQuantityTypeIdentifierActiveEnergyBurned", "HKQuantityTypeIdentifierAppleExerciseTime",
    "HKQuantityTypeIdentifierRespiratoryRate", "HKQuantityTypeIdentifierTimeInDaylight",
    "HKCategoryTypeIdentifierMindfulSession",
]
CARE_TEAM = [
    {"clinician_id": "cl_2b81e04d", "name": "Dr. Lena Ortiz, LPC", "role": "primary_therapist"},
    {"clinician_id": "cl_9c44a7e1", "name": "Dr. Sam Whitfield, MD", "role": "prescriber"},
]


def d(i):
    return START + timedelta(days=i)


def ts(day_i, h, m=0):
    return (datetime.combine(d(day_i), time(0, 0)) + timedelta(hours=h, minutes=m)).strftime("%Y-%m-%dT%H:%M:%S") + TZ


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def band_phq9(t):
    return "minimal" if t <= 4 else "mild" if t <= 9 else "moderate" if t <= 14 else "moderately_severe" if t <= 19 else "severe"


def band_gad7(t):
    return "minimal" if t <= 4 else "mild" if t <= 9 else "moderate" if t <= 14 else "severe"


def difficulty(t):
    return "very_difficult" if t >= 15 else "somewhat_difficult" if t >= 8 else "not_difficult_at_all"


def curve(knots):
    """Piecewise-linear latent wellbeing h(day) in [0,1]."""
    def h(day):
        for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
            if x0 <= day <= x1:
                return y0 + (y1 - y0) * (day - x0) / (x1 - x0)
        return knots[-1][1]
    return h


def spread(total, n, weights, cap=3):
    """Distribute an integer total across n items proportionally to weights, each 0..cap."""
    items = [0] * n
    remaining = total
    order = sorted(range(n), key=lambda i: -weights[i])
    while remaining > 0:
        progressed = False
        for i in order:
            if remaining and items[i] < cap and random.random() < weights[i]:
                items[i] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            for i in order:
                if remaining and items[i] < cap:
                    items[i] += 1
                    remaining -= 1
    return items


def generate(p):
    random.seed(p["seed"])
    pid, h = p["patient_id"], curve(p["knots"])
    uid = lambda prefix: f"{prefix}_{uuid.UUID(int=random.getrandbits(128)).hex[:12]}"  # noqa: E731
    out = ROOT / pid
    out.mkdir(parents=True, exist_ok=True)

    sessions = [{
        "session_id": f"ses_{k+1:02d}", "session_number": k + 1, "scheduled_start": ts(1 + 7 * k, p["session_hour"]),
        "duration_min": 53 if p["diagnoses"] else 30,
        "modality": "telehealth" if k in p["telehealth_weeks"] else "in_person",
        "cpt_code": ("90791" if k == 0 else "90837") if p["diagnoses"] else "96127",
        "attended": k not in p["missed_weeks"],
    } for k in range(12)]

    patient = {
        "_synthetic": True, "_generated_at": "2026-10-08T19:30:00" + TZ,
        "patient_id": pid, "display_name": p["display_name"], "date_of_birth": p["dob"],
        "sex_at_birth": p["sex"], "pronouns": p["pronouns"], "timezone": "America/New_York",
        "enrollment": {
            "enrolled_at": ts(0, 18, random.randint(0, 50)), "program": p["program"],
            "observation_window": {"start": str(d(0)), "end": str(d(DAYS - 1))}, "practices_start": str(d(7)),
            "consents": {"self_report_sharing": True, "healthkit_sharing": True, "healthkit_types_authorized": HK_TYPES,
                         "journal_ai_summary": True, "voice_note_transcription": True},
            "devices": [{"type": "iPhone", "model": p["phone"], "os": "iOS 19.6"},
                        {"type": "Apple Watch", "model": p["watch"], "os": "watchOS 12.6"}],
        },
        "clinical": {
            "primary_diagnosis": p["diagnoses"][0] if p["diagnoses"] else None,
            "secondary_diagnoses": p["diagnoses"][1:], "medications": p["medications"],
            "treatment_modality": p["modality"], "intake_phq9_total": None,
        },
        "care_team": CARE_TEAM if p["diagnoses"] else CARE_TEAM[:1],
        "sessions": sessions,
        "clinical_events": p["events"],
    }

    # --- weekly instruments, totals driven by h ---
    def instrument(items_text, lo, hi, weights, band_fn, key):
        """Weekly totals interpolate from `lo` (at h=0) to `hi` (at h=1)."""
        rows = []
        for k in range(12):
            day = 7 * k
            total = int(clamp(round(lo + (hi - lo) * h(day) + random.gauss(0, 0.8)), 0, 3 * len(items_text)))
            items = spread(total, len(items_text), weights)
            if key == "phq9":
                items[8] = 0  # no item-9 positives in this cohort
                total = sum(items)
            rows.append({
                "response_id": uid(key), "instrument": "PHQ-9" if key == "phq9" else "GAD-7",
                "administration_week": k, "completed_at": ts(day, 20, random.randint(5, 50)),
                "items": [{"item": i + 1, "text": t, "score": s} for i, (t, s) in enumerate(zip(items_text, items))],
                "total_score": total, "severity_band": band_fn(total),
                "functional_difficulty": difficulty(total),
            })
        return rows
    patient["clinical"]["intake_phq9_total"] = None
    phq9 = instrument(PHQ9_ITEMS, *p["phq9_range"], p["phq9_weights"], band_phq9, "phq9")
    patient["clinical"]["intake_phq9_total"] = phq9[0]["total_score"]
    gad7 = instrument(GAD7_ITEMS, *p["gad7_range"], [1] * 7, band_gad7, "gad7") if p.get("gad7_range") else []

    # --- daily mood ---
    mood = []
    for i in range(DAYS):
        if random.random() > p["adherence"](i):
            continue
        hv = h(i)
        m = clamp(round(p["mood_base"] + p["mood_span"] * hv + random.gauss(0, 0.7)), 1, 10)
        anx = clamp(round(p["anx_base"] - p["anx_span"] * hv + random.gauss(0, 0.8)), 1, 10)
        en = clamp(round(p["en_base"] + p["en_span"] * hv + random.gauss(0, 0.9)), 1, 10)
        pool = EMO["low"] if m <= 4 else EMO["mid"] if m <= 6 else EMO["high"]
        tags = sorted(set(random.sample(pool, k=random.choice([1, 2, 2, 3]))))
        mood.append({
            "checkin_id": uid("mood"), "logged_at": ts(i, random.choice([8, 21]), random.randint(0, 59)),
            "mood": m, "anxiety": anx, "energy": en,
            "scale": "1-10 (10 = best for mood/energy; 10 = worst for anxiety)",
            "emotion_tags": tags, "note": p["notes"].get(i),
        })

    # --- journals (1/week, Wed) and voice notes (every other week, Sat) ---
    journal = [{
        "entry_id": uid("jrn"), "created_at": ts(7 * w + 2, 22, random.randint(0, 50)), "text": text,
        "word_count": len(text.split()), "ai_summary": summ, "ai_themes": themes, "sentiment_score": sent,
        "sentiment_scale": "-1 (very negative) to +1 (very positive)", "shared_with_clinician": True,
    } for w, (text, summ, themes, sent) in enumerate(p["journals"])]
    voice = [{
        "voice_note_id": uid("vn"), "recorded_at": ts(14 * k + 5, random.choice([8, 12, 18]), random.randint(0, 59)),
        "duration_sec": int(len(text.split()) / 2.2 + random.randint(3, 12)),
        "audio_uri": f"s3://carelinq-demo/audio/{pid}/vn_w{2*k:02d}.m4a", "transcript": text,
        "transcription_confidence": round(random.uniform(0.88, 0.97), 2), "ai_summary": summ,
        "sentiment_score": sent, "shared_with_clinician": True,
    } for k, (text, summ, sent) in enumerate(p["voice"])]

    # --- practices ---
    defs = [{"practice_id": f"prc_{k}", "name": n, "track": "make_it_happen", "target_per_week": tgt,
             "created_at": ts(8, 18, 30 + j)} for j, (k, n, tgt) in enumerate(p["practices"])]
    defs.append({"practice_id": "prc_name", "name": "Pause and name the feeling", "track": "meet_the_moment",
                 "target_per_week": None, "trigger": "When I notice a surge of stress", "created_at": ts(8, 18, 40)})
    logs = [{"log_id": uid("plog"), "practice_id": pr["practice_id"], "date": str(d(i)),
             "completed": random.random() < p["practice_rate"](pr["practice_id"][4:], h(i))}
            for i in range(8, DAYS) for pr in defs[:-1]]
    cycles = []
    for w in range(1, 12):
        for pr in defs[:-1]:
            done = sum(1 for l in logs if l["practice_id"] == pr["practice_id"] and l["completed"]
                       and 7 * w <= (date.fromisoformat(l["date"]) - START).days < 7 * w + 7)
            cycles.append({"practice_id": pr["practice_id"], "week": w, "cycle_start": str(d(7 * w)),
                           "cycle_end": str(d(7 * w + 6)), "target": pr["target_per_week"], "completed": done,
                           "met_target": done >= pr["target_per_week"]})
    mtm = []
    for i in range(7, DAYS):
        if random.random() < p["mtm_rate"]:
            sit, emo = random.choice(p["situations"])
            before = clamp(round(7.5 - 3 * h(i) + random.gauss(0, 0.8)), 2, 10)
            mtm.append({"log_id": uid("mtm"), "practice_id": "prc_name",
                        "logged_at": ts(i, random.randint(9, 22), random.randint(0, 59)),
                        "situation": sit, "emotion_named": emo, "intensity_before": before,
                        "intensity_after": clamp(before - random.choice([1, 2, 2, 3]), 1, 10),
                        "scale": "0-10 subjective distress"})

    self_report = {"_synthetic": True, "patient_id": pid, "phq9_responses": phq9, "gad7_responses": gad7,
                   "mood_checkins": mood, "journal_entries": journal, "voice_notes": voice,
                   "practices": {"definitions": defs, "daily_logs": logs, "weekly_cycles": cycles,
                                 "meet_the_moment_logs": mtm}}

    # --- healthkit ---
    lerp = lambda lo, hi, i, sd: lo + (hi - lo) * h(i) + random.gauss(0, sd)  # noqa: E731
    sleep, daily = [], []
    for i in range(DAYS):
        worn = random.random() > 0.06
        if worn and i < DAYS - 1:
            asleep = clamp(lerp(*p["sleep_min"], i, 25), 220, 560)
            latency = clamp(lerp(*p["latency"], i, 6), 3, 90)
            awake = clamp(lerp(*p["awake"], i, 7), 3, 120)
            bed_off = clamp(lerp(*p["bed_offset"], i, 20), -120, 150)
            deep = asleep * clamp(random.gauss(0.11 + 0.04 * h(i), 0.015), 0.06, 0.2)
            rem = asleep * clamp(random.gauss(0.19 + 0.04 * h(i), 0.02), 0.12, 0.28)
            start = datetime.combine(d(i + 1), time(0, 0)) + timedelta(minutes=bed_off)
            end = start + timedelta(minutes=latency + asleep + awake)
            sleep.append({
                "night_of": str(d(i)), "hk_type": "HKCategoryTypeIdentifierSleepAnalysis", "source": "Apple Watch",
                "in_bed_start": start.strftime("%Y-%m-%dT%H:%M:%S") + TZ, "in_bed_end": end.strftime("%Y-%m-%dT%H:%M:%S") + TZ,
                "sleep_onset_latency_min": round(latency), "total_asleep_min": round(asleep), "awake_min": round(awake),
                "awakenings": int(clamp(round(lerp(5, 1.5, i, 1)), 0, 10)),
                "stages_min": {"asleepCore": round(asleep - deep - rem), "asleepDeep": round(deep), "asleepREM": round(rem), "awake": round(awake)},
                "sleep_efficiency": round(asleep / (latency + asleep + awake), 3),
            })
        steps = max(400, int(lerp(*p["steps"], i, 900)))
        ex = max(0, round(lerp(*p["exercise"], i, 6)))
        daily.append({
            "date": str(d(i)), "watch_worn": worn,
            "HKQuantityTypeIdentifierStepCount": {"value": steps, "unit": "count", "source": "iPhone+Watch"},
            "HKQuantityTypeIdentifierActiveEnergyBurned": {"value": round(steps * 0.038 + ex * 6.5 + random.gauss(40, 20)), "unit": "kcal"},
            "HKQuantityTypeIdentifierAppleExerciseTime": {"value": ex if worn else None, "unit": "min"},
            "HKQuantityTypeIdentifierRestingHeartRate": {"value": round(lerp(*p["rhr"], i, 1.6)) if worn else None, "unit": "count/min"},
            "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": {"value": round(clamp(lerp(*p["hrv"], i, 4.5), 12, 110), 1) if worn else None,
                                                                "unit": "ms", "aggregation": "daily_mean_of_samples"},
            "HKQuantityTypeIdentifierRespiratoryRate": {"value": round(lerp(16.2, 14.6, i, 0.4), 1) if worn else None,
                                                        "unit": "count/min", "aggregation": "sleep_mean"},
            "HKQuantityTypeIdentifierTimeInDaylight": {"value": max(0, round(lerp(*p["daylight"], i, 10))) if worn else None, "unit": "min"},
            "HKCategoryTypeIdentifierMindfulSession": {"value": (random.choice([3, 5, 10]) if random.random() < 0.1 + 0.4 * h(i) else 0), "unit": "min"},
        })
    healthkit = {"_synthetic": True, "patient_id": pid, "sleep_sessions": sleep, "daily_metrics": daily}

    for name, obj in [("patient.json", patient), ("self_report.json", self_report), ("healthkit.json", healthkit)]:
        (out / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    (out / "behavidence.json").write_text(json.dumps(behavidence(pid, h, p["mhss"]), indent=2))
    print(pid, p["display_name"], "phq9", [r["total_score"] for r in phq9],
          "gad7", [r["total_score"] for r in gad7], "mood", len(mood), "sleep", len(sleep))


def behavidence(pid, h, m):
    """Daily Behavidence MHSS similarity scores (0-100). Phone-based, ~8% days missing."""
    rows = []
    for i in range(DAYS):
        if random.random() < 0.08:
            continue
        hv = h(i)
        rows.append({"date": str(d(i)),
                     "anxiety": int(clamp(round(m["anxiety"][0] - m["anxiety"][1] * hv + random.gauss(0, 4)), 0, 100)),
                     "stress": int(clamp(round(m["stress"][0] - m["stress"][1] * hv + random.gauss(0, 4)), 0, 100)),
                     "depression": int(clamp(round(m["depression"][0] - m["depression"][1] * hv + random.gauss(0, 5)), 0, 100)),
                     "adhd": int(clamp(round(m["adhd"][0] - m["adhd"][1] * hv + random.gauss(0, 4)), 0, 100))})
    return {"_synthetic": True, "patient_id": pid, "source": "Behavidence MHSS", "unit": "percent", "daily": rows}


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

DANIEL = {
    "seed": 7, "patient_id": "pt_b2c4e8d1", "display_name": "Daniel K.", "dob": "1988-11-02",
    "sex": "male", "pronouns": "he/him", "phone": "iPhone 16", "watch": "Apple Watch Series 10",
    "program": "between_session_support", "modality": "CBT with exposure work, weekly 53-min sessions",
    "diagnoses": [{"icd10": "F41.1", "description": "Generalized anxiety disorder"},
                  {"icd10": "F90.0", "description": "ADHD, predominantly inattentive type"}],
    "medications": [{"name": "escitalopram", "dose": "10 mg", "frequency": "daily", "started": "2026-06-15"},
                    {"name": "methylphenidate ER", "dose": "36 mg", "frequency": "daily, morning", "started": "2025-11-03"}],
    "session_hour": 18, "telehealth_weeks": {2, 6, 10}, "missed_weeks": {7},
    # anxiety-driven: slow gains, product-launch crunch in weeks 6-8, recovery after
    "knots": [(0, 0.15), (35, 0.55), (42, 0.5), (50, 0.2), (58, 0.3), (83, 0.72)],
    "phq9_range": (12, 5), "phq9_weights": [0.5, 0.5, 0.8, 0.8, 0.3, 0.5, 0.9, 0.7, 0.0],
    "gad7_range": (17, 7),
    "mood_base": 3.8, "mood_span": 4.0, "anx_base": 9.0, "anx_span": 5.5, "en_base": 3.5, "en_span": 3.5,
    "adherence": lambda i: 0.85 if i < 42 else 0.6 if i < 56 else 0.82,
    "notes": {43: "Launch moved up two weeks. Everyone is losing it.", 49: "Slept 3 hours. Heart was pounding all night.",
              55: "Launch shipped. I did not break anything.", 70: "Forgot my meds twice this week, noticed by Wednesday."},
    "journals": [
        ("First entry. Dr. Ortiz wants me to write when the worry spiral starts. It started at 6am about a meeting that isn't until Thursday.", "Anticipatory worry days ahead of a work event.", ["rumination", "work", "anxiety"], -0.45),
        ("I rewrote the same email four times. I know it's the ADHD plus the anxiety feeding each other but knowing doesn't stop it.", "Perfectionism loop around a work email; insight without relief.", ["work", "perfectionism", "adhd"], -0.4),
        ("Tried the 10-minute worry window. Weird to schedule worrying but I actually stopped at the timer.", "First use of scheduled worry time with success.", ["coping_skill", "therapy"], 0.2),
        ("Ran before work three times. Mornings are less jittery when I do. The med timer on my watch is helping.", "Exercise and medication routine reducing morning anxiety.", ["exercise", "routine", "medication"], 0.4),
        ("Best week in a while. Finished the planning doc a day early. Nobody died.", "Improved task completion; self-deprecating humor.", ["work", "self_efficacy"], 0.55),
        ("Ran into my old manager at the coffee place and didn't freeze. Said something normal. Progress.", "Social exposure handled well.", ["social_connection", "exposure"], 0.5),
        ("Launch got pulled in by two weeks. I am back to 4am wakeups and chest tightness. Skipped the run all week.", "Acute work stressor; sleep disruption and lapsed exercise.", ["work", "acute_stressor", "sleep", "practice_lapse"], -0.7),
        ("Missed session because of a release call. Took a double dose of coffee instead of eating. Not great.", "Missed therapy; poor self-care during crunch.", ["work", "practice_lapse", "self_care"], -0.6),
        ("Shipped. Slept 9 hours. Then spent the whole weekend convinced something would break. Nothing did.", "Post-launch relief with lingering catastrophic worry.", ["work", "catastrophizing", "relief"], -0.1),
        ("Back to running. Did the thought record on the 'they'll find out I'm a fraud' thought. Evidence against was long.", "Resumed exercise; cognitive restructuring applied to imposter thought.", ["exercise", "cognitive_restructuring", "self_criticism"], 0.35),
        ("Noticed I forgot meds two days and the fog was obvious. Set a second alarm. Mood fine though.", "Medication adherence slip caught quickly.", ["medication", "adhd", "routine"], 0.3),
        ("Presented to leadership. Heart rate on the watch was 110 but I got through it and it was fine. Dr. Ortiz says that's the whole point.", "Exposure to feared presentation completed successfully.", ["exposure", "work", "self_efficacy"], 0.62),
    ],
    "voice": [
        ("Okay. Uh, it's Saturday and I've been thinking about Monday since I woke up. That's the thing I'm supposed to notice. Noticed.", "Anticipatory anxiety about the work week.", -0.35),
        ("Ran this morning. Legs hurt, brain quiet for like twenty minutes. Worth it.", "Exercise producing short mental quiet.", 0.4),
        ("Had a good week. I keep waiting for the catch. That's probably a thing to bring up.", "Positive week with anticipatory doubt.", 0.3),
        ("It's 4am again. Launch stuff. I'm not going to get back to sleep so I'm just saying it out loud.", "Early-morning waking under work stress.", -0.65),
        ("Launch is done. I feel like I ran a marathon and I'm angry at myself for how much it took out of me.", "Post-launch exhaustion with self-directed frustration.", -0.2),
        ("Presentation went fine. Hands shook but nobody noticed, or they didn't care. Either way.", "Successful exposure; tolerated visible anxiety.", 0.55),
    ],
    "practices": [("run", "Morning run (25 min)", 3), ("meds", "Take escitalopram + methylphenidate", 7),
                  ("worry", "10-min worry window", 5), ("reach", "Text or call a friend", 2)],
    "practice_rate": lambda k, hv: {"run": 0.2 + 0.6 * hv, "meds": 0.8 + 0.18 * hv, "worry": 0.3 + 0.55 * hv, "reach": 0.1 + 0.3 * hv}[k],
    "mtm_rate": 0.3,
    "situations": [("Slack message from VP with no context", "dread"), ("Calendar invite titled 'quick sync'", "anxious"),
                   ("Realized I forgot a deadline", "ashamed"), ("Crowded train, couldn't get off", "overwhelmed"),
                   ("Code review with a lot of comments", "embarrassed")],
    "sleep_min": (330, 420), "latency": (38, 14), "awake": (40, 15), "bed_offset": (45, -30),
    "steps": (4200, 8200), "exercise": (8, 30), "rhr": (74, 64), "hrv": (26, 44), "daylight": (20, 55),
    "mhss": {"anxiety": (88, 40), "stress": (62, 30), "depression": (48, 25), "adhd": (80, 20)},
    "events": [
        {"category": "psychosocial_stressor", "label": "work_crunch", "description": "Product launch pulled in by two weeks", "onset_at": "2026-08-25T09:00:00-04:00", "resolved_at": "2026-09-06T18:00:00-04:00", "valence": -1},
        {"category": "milestone", "label": "launch_shipped", "description": "Launch shipped without incident", "onset_at": "2026-09-06T18:00:00-04:00", "resolved_at": None, "valence": 1},
        {"category": "milestone", "label": "exposure_completed", "description": "Presented to leadership (feared situation)", "onset_at": "2026-10-01T15:00:00-04:00", "resolved_at": None, "valence": 1},
    ],
}

ELENA = {
    "seed": 11, "patient_id": "pt_c9d1a3f7", "display_name": "Elena M.", "dob": "1995-04-27",
    "sex": "female", "pronouns": "she/her", "phone": "iPhone 15", "watch": "Apple Watch SE",
    "program": "wellness_monitoring", "modality": "Wellness check-ins, 30-min monthly", "diagnoses": [], "medications": [],
    "session_hour": 12, "telehealth_weeks": {1, 2, 3, 5, 6, 7, 9, 10, 11}, "missed_weeks": set(),
    "knots": [(0, 0.78), (30, 0.86), (55, 0.82), (83, 0.9)],
    "phq9_range": (4, 1), "phq9_weights": [0.3, 0.2, 0.6, 0.7, 0.3, 0.2, 0.4, 0.2, 0.0],
    "mood_base": 5.0, "mood_span": 4.0, "anx_base": 5.5, "anx_span": 3.5, "en_base": 4.5, "en_span": 4.0,
    "adherence": lambda i: 0.75,
    "notes": {20: "Half marathon training started.", 61: "Long week but a good one."},
    "journals": [
        ("Signed up for the wellness program mostly for the sleep tracking. Felt fine this week, a bit tired from the move.", "Baseline check-in; mild fatigue from relocation.", ["routine", "sleep"], 0.2),
        ("Unpacked the last box. Ran along the river for the first time here. Nice.", "Settling in; exercise and enjoyment.", ["exercise", "pleasure"], 0.6),
        ("Started half marathon training. Legs are complaining, head is clear.", "New fitness goal; positive affect.", ["exercise", "self_efficacy"], 0.65),
        ("Dinner with the new team. I was nervous for about five minutes and then it was just dinner.", "Brief social nerves, resolved; connected.", ["social_connection"], 0.55),
        ("Quiet week. Read two books. Slept great.", "Rest and recovery week.", ["sleep", "pleasure"], 0.6),
        ("Mom visited. Lovely but exhausting. Need a day to myself.", "Family visit; mild social fatigue.", ["family", "self_care"], 0.3),
        ("Long run, 14k. Cried a little at the end, the good kind.", "Training milestone; positive emotional release.", ["exercise", "pleasure"], 0.75),
        ("Work got busy with the quarter end. Sleep a bit shorter. Still fine.", "Transient work load; minor sleep impact.", ["work", "sleep"], 0.1),
        ("Quarter closed. Took Friday off and did nothing. Perfect.", "Recovery after busy period.", ["work", "self_care"], 0.6),
        ("Race in two weeks. Tapering makes me antsy but it's a good antsy.", "Pre-race restlessness, positive framing.", ["exercise"], 0.5),
        ("Ran the half. 1:58. Everyone came. Best day in a long time.", "Completed race; strong social support.", ["exercise", "social_connection", "pleasure"], 0.9),
        ("Post-race slump for a day, then fine. Thinking about what's next.", "Brief post-goal dip; forward-looking.", ["exercise", "identity"], 0.5),
    ],
    "voice": [
        ("Hey, first note. Mostly good. Tired from unpacking. That's it.", "Baseline; mild fatigue.", 0.3),
        ("Did my long run. Feeling strong. Honestly nothing to report.", "Training going well.", 0.6),
        ("Busy week at work, bit short on sleep. Nothing worrying.", "Transient busyness.", 0.2),
        ("Race day tomorrow. Nervous, excited, both.", "Pre-race anticipation.", 0.5),
        ("Finished! I'm so happy. Okay bye.", "Race completed; elated.", 0.9),
        ("Back to normal. Thinking about signing up for the full next year.", "Post-race planning.", 0.55),
    ],
    "practices": [("run", "Training run", 4), ("bed", "Lights out by 11pm", 5), ("water", "2L water", 7)],
    "practice_rate": lambda k, hv: {"run": 0.55 + 0.35 * hv, "bed": 0.5 + 0.4 * hv, "water": 0.7 + 0.25 * hv}[k],
    "mtm_rate": 0.06,
    "situations": [("Email from landlord", "anxious"), ("Missed a train", "irritated"), ("Big group chat", "overwhelmed")],
    "sleep_min": (420, 450), "latency": (14, 9), "awake": (16, 10), "bed_offset": (-40, -60),
    "steps": (8500, 11500), "exercise": (35, 50), "rhr": (58, 54), "hrv": (62, 74), "daylight": (55, 80),
    "mhss": {"anxiety": (34, 14), "stress": (40, 18), "depression": (26, 10), "adhd": (30, 8)},
    "events": [
        {"category": "milestone", "label": "race_completed", "description": "Completed half marathon", "onset_at": "2026-09-27T10:30:00-04:00", "resolved_at": None, "valence": 1},
    ],
}

MARCUS = {
    "seed": 23, "patient_id": "pt_d4e6b2a9", "display_name": "Marcus T.", "dob": "1979-09-14",
    "sex": "male", "pronouns": "he/him", "phone": "iPhone 14", "watch": "Apple Watch Series 8",
    "program": "wellness_monitoring", "modality": "Wellness check-ins, 30-min monthly", "diagnoses": [], "medications": [],
    "session_hour": 8, "telehealth_weeks": {1, 2, 3, 4, 5, 6, 7, 9, 10, 11}, "missed_weeks": {5},
    # steady, with a one-week dip for a bad cold + travel in week 6
    "knots": [(0, 0.76), (38, 0.82), (42, 0.55), (49, 0.6), (56, 0.8), (83, 0.84)],
    "phq9_range": (5, 1), "phq9_weights": [0.2, 0.2, 0.7, 0.8, 0.4, 0.1, 0.4, 0.2, 0.0],
    "mood_base": 5.2, "mood_span": 3.5, "anx_base": 5.0, "anx_span": 3.0, "en_base": 4.0, "en_span": 4.0,
    "adherence": lambda i: 0.6 if 42 <= i < 49 else 0.7,
    "notes": {42: "Flew to Denver for the conference. Came back with a cold.", 46: "Still sick. Skipped everything."},
    "journals": [
        ("My wife signed us both up for this. Fine. Slept okay, kids are on summer schedule so mornings are loud.", "Baseline; family routine.", ["family", "routine"], 0.3),
        ("Coached the under-10s Saturday. We lost 6-1 and they were thrilled anyway.", "Enjoyable family and community activity.", ["family", "pleasure"], 0.6),
        ("Work's steady. Started walking at lunch instead of eating at my desk.", "New lunchtime walk habit.", ["work", "exercise", "routine"], 0.45),
        ("Back-to-school chaos. Forms, shoes, a lost backpack. Normal.", "Family logistics; neutral.", ["family"], 0.2),
        ("Long weekend at the lake. No phone for two days. Should do that more.", "Restorative time off; low screen use.", ["pleasure", "self_care"], 0.7),
        ("Denver conference. Good talks, bad sleep, came home with a cold.", "Travel and illness onset.", ["work", "sleep", "illness"], -0.1),
        ("Sick all week. Couch, tea, nothing done. Grumpy about it.", "Acute illness; low energy and irritability.", ["illness", "low_energy"], -0.35),
        ("Mostly better. Walks are back. Appetite's back.", "Recovery from illness.", ["illness", "routine"], 0.3),
        ("Our team hit its number. Took everyone out. Good night.", "Work success and social time.", ["work", "social_connection"], 0.6),
        ("Daughter's recital. She nailed it. I may have gotten something in my eye.", "Family pride.", ["family", "pleasure"], 0.8),
        ("Quiet. Fixed the fence. Slept nine hours Saturday.", "Rest and home projects.", ["sleep", "pleasure"], 0.55),
        ("Three months in. Honestly nothing dramatic to report, which I think is the point.", "Stable period; reflective.", ["identity"], 0.5),
    ],
    "voice": [
        ("Testing. Uh, day's fine. Kids are feral. That's all.", "Baseline; family humor.", 0.3),
        ("Lunch walk done. Trying to make it a thing.", "Habit formation.", 0.4),
        ("I'm sick. Voice is gone, so this is short.", "Acute illness.", -0.3),
        ("Better. Back to walking. Appetite is definitely back.", "Illness recovery.", 0.35),
        ("Recital was tonight. She was great. Proud dad noise.", "Family pride.", 0.8),
        ("Nothing to report. Good week. Bye.", "Stable.", 0.5),
    ],
    "practices": [("walk", "Lunch walk (20 min)", 4), ("bed", "Lights out by 11pm", 5), ("family", "Phone-free dinner", 5)],
    "practice_rate": lambda k, hv: {"walk": 0.45 + 0.4 * hv, "bed": 0.45 + 0.4 * hv, "family": 0.6 + 0.3 * hv}[k],
    "mtm_rate": 0.05,
    "situations": [("Kid meltdown in the car", "frustrated"), ("Budget review", "tense"), ("Airport delay", "irritated")],
    "sleep_min": (400, 430), "latency": (18, 12), "awake": (22, 14), "bed_offset": (-20, -45),
    "steps": (6500, 9500), "exercise": (20, 32), "rhr": (64, 60), "hrv": (44, 52), "daylight": (40, 60),
    "mhss": {"anxiety": (36, 12), "stress": (46, 16), "depression": (30, 12), "adhd": (34, 8)},
    "events": [
        {"category": "medical", "label": "acute_illness", "description": "Upper respiratory infection after travel", "onset_at": "2026-08-24T20:00:00-04:00", "resolved_at": "2026-09-01T08:00:00-04:00", "valence": -1},
    ],
}

# Maya's latent curve, copied from her generator so her MHSS stream co-moves with everything else.
MAYA_KNOTS = [(0, 0.05), (37, 0.62), (40, 0.48), (52, 0.10), (60, 0.30), (83, 0.92)]
MAYA_MHSS = {"anxiety": (90, 45), "stress": (55, 25), "depression": (88, 55), "adhd": (62, 20)}

if __name__ == "__main__":
    for profile in (DANIEL, ELENA, MARCUS):
        generate(profile)
    random.seed(42)
    (ROOT / "pt_7f3a9c21" / "behavidence.json").write_text(
        json.dumps(behavidence("pt_7f3a9c21", curve(MAYA_KNOTS), MAYA_MHSS), indent=2))
    print("pt_7f3a9c21 Maya R. behavidence.json written")
