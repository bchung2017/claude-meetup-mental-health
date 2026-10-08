"""
Synthetic between-session data generator: 1 patient, 12 weeks.
All people, names and events are fictional. Seeded for reproducibility.
Narrative arc: improve (wk 0-5) -> stressor + dip (wk 5-8) -> recover (wk 8-11).
"""
import json, random, math, os, uuid
from datetime import date, datetime, timedelta, time

random.seed(42)
OUT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)

TZ = "-04:00"
START = date(2026, 7, 13)          # Monday, enrollment / Week 0
DAYS = 84                          # 12 weeks, through Sun 2026-10-04
PATIENT_ID = "pt_7f3a9c21"
CLINICIAN_ID = "cl_2b81e04d"

def d(i): return START + timedelta(days=i)
def ts(day_i, h, m=0, s=0):
    dt = datetime.combine(d(day_i), time(0, 0)) + timedelta(hours=h, minutes=m, seconds=s)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + TZ
def uid(prefix): return f"{prefix}_{uuid.UUID(int=random.getrandbits(128)).hex[:12]}"
def clamp(x, lo, hi): return max(lo, min(hi, x))

# ---- latent "wellbeing" index h(day) in [0,1] driving every stream ----
KNOTS = [(0, 0.05), (37, 0.62), (40, 0.48), (52, 0.10), (60, 0.30), (83, 0.92)]
def h(day):
    for (x0, y0), (x1, y1) in zip(KNOTS, KNOTS[1:]):
        if x0 <= day <= x1:
            return y0 + (y1 - y0) * (day - x0) / (x1 - x0)
    return KNOTS[-1][1]
def phase(day):
    if day < 21: return "baseline"
    if day < 38: return "improving"
    if day < 56: return "stressor_dip"
    return "recovery"
STRESSOR_DAY = 38  # Thu 2026-08-20: layoff announced at work

# =====================================================================
# patient.json
# =====================================================================
sessions = []
for k in range(12):
    sd = 1 + 7 * k  # Tuesdays
    sessions.append({
        "session_id": f"ses_{k+1:02d}",
        "session_number": k + 1,
        "scheduled_start": ts(sd, 17, 0),
        "duration_min": 53,
        "modality": "telehealth" if k in (3, 8) else "in_person",
        "cpt_code": "90791" if k == 0 else "90837",
        "attended": True,
    })

patient = {
    "_synthetic": True,
    "_generated_at": "2026-10-08T18:45:00" + TZ,
    "patient_id": PATIENT_ID,
    "display_name": "Maya R.",
    "date_of_birth": "1992-03-19",
    "sex_at_birth": "female",
    "pronouns": "she/her",
    "timezone": "America/New_York",
    "enrollment": {
        "enrolled_at": ts(0, 18, 12),
        "program": "between_session_support",
        "observation_window": {"start": str(d(0)), "end": str(d(DAYS - 1))},
        "practices_start": str(d(7)),  # Week 0 is an enrollment buffer
        "consents": {
            "self_report_sharing": True,
            "healthkit_sharing": True,
            "healthkit_types_authorized": [
                "HKCategoryTypeIdentifierSleepAnalysis",
                "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
                "HKQuantityTypeIdentifierRestingHeartRate",
                "HKQuantityTypeIdentifierStepCount",
                "HKQuantityTypeIdentifierActiveEnergyBurned",
                "HKQuantityTypeIdentifierAppleExerciseTime",
                "HKQuantityTypeIdentifierRespiratoryRate",
                "HKQuantityTypeIdentifierTimeInDaylight",
                "HKCategoryTypeIdentifierMindfulSession",
            ],
            "journal_ai_summary": True,
            "voice_note_transcription": True,
        },
        "devices": [
            {"type": "iPhone", "model": "iPhone 15", "os": "iOS 19.6"},
            {"type": "Apple Watch", "model": "Apple Watch Series 9", "os": "watchOS 12.6"},
        ],
    },
    "clinical": {
        "primary_diagnosis": {"icd10": "F33.1", "description": "Major depressive disorder, recurrent, moderate"},
        "secondary_diagnoses": [{"icd10": "G47.00", "description": "Insomnia, unspecified"}],
        "medications": [{"name": "sertraline", "dose": "50 mg", "frequency": "daily", "started": "2026-05-02"}],
        "treatment_modality": "CBT, weekly 53-min sessions",
        "intake_phq9_total": 18,
    },
    "care_team": [
        {"clinician_id": CLINICIAN_ID, "name": "Dr. Lena Ortiz, LPC", "role": "primary_therapist"},
        {"clinician_id": "cl_9c44a7e1", "name": "Dr. Sam Whitfield, MD", "role": "prescriber"},
    ],
    "sessions": sessions,
}

# =====================================================================
# self_report.json
# =====================================================================
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
PHQ9_ITEM_SCORES = [
    [2,3,3,3,2,2,2,1,0], [2,3,3,2,2,2,2,1,0], [2,2,3,2,2,2,1,1,0], [2,2,2,2,1,2,1,1,0],
    [1,2,2,2,1,1,1,1,0], [1,1,2,2,1,1,1,1,0], [1,2,3,2,1,2,1,1,0], [2,2,3,2,2,2,2,0,1],
    [2,2,2,2,1,2,2,1,0], [1,2,2,2,1,2,1,1,0], [1,1,1,2,1,1,1,1,0], [1,1,1,1,1,1,1,0,0],
]
DIFFICULTY = ["not_difficult_at_all", "somewhat_difficult", "very_difficult", "extremely_difficult"]
def band(t):
    return "minimal" if t <= 4 else "mild" if t <= 9 else "moderate" if t <= 14 else "moderately_severe" if t <= 19 else "severe"

phq9 = []
for k, items in enumerate(PHQ9_ITEM_SCORES):
    day = 7 * k  # Mondays, the evening before session
    total = sum(items)
    phq9.append({
        "response_id": uid("phq"),
        "instrument": "PHQ-9",
        "administration_week": k,
        "completed_at": ts(day, 20, random.randint(5, 50)),
        "items": [{"item": i + 1, "text": PHQ9_ITEMS[i], "score": s} for i, s in enumerate(items)],
        "total_score": total,
        "severity_band": band(total),
        "functional_difficulty": DIFFICULTY[2 if total >= 15 else 1 if total >= 8 else 0],
    })

# --- daily mood check-ins ---
EMO = {
    "low":  ["hopeless", "numb", "drained", "ashamed", "lonely", "dread", "irritable", "overwhelmed"],
    "mid":  ["restless", "flat", "uncertain", "tired", "wistful", "tense", "okay", "hopeful"],
    "high": ["content", "calm", "grateful", "energized", "proud", "connected", "relieved", "curious"],
}
ADHERENCE = {"baseline": 0.80, "improving": 0.92, "stressor_dip": 0.62, "recovery": 0.88}
mood = []
for i in range(DAYS):
    ph = phase(i)
    if random.random() > ADHERENCE[ph]:
        continue
    hv = h(i)
    weekend = d(i).weekday() >= 5
    m = clamp(round(2.6 + 5.0 * hv + random.gauss(0, 0.8) + (0.3 if weekend else 0)), 1, 10)
    anx = clamp(round(8.2 - 5.0 * hv + random.gauss(0, 0.9) + (1.2 if STRESSOR_DAY <= i < 50 else 0)), 1, 10)
    en = clamp(round(2.5 + 5.0 * hv + random.gauss(0, 1.0)), 1, 10)
    pool = EMO["low"] if m <= 4 else EMO["mid"] if m <= 6 else EMO["high"]
    tags = random.sample(pool, k=random.choice([1, 2, 2, 3]))
    if 4 <= m <= 7 and random.random() < 0.3:
        tags.append(random.choice(EMO["mid"] if m > 5 else EMO["low"]))
    mood.append({
        "checkin_id": uid("mood"),
        "logged_at": ts(i, 21, random.randint(0, 59)) if random.random() < 0.7 else ts(i, 8, random.randint(0, 59)),
        "mood": m, "anxiety": anx, "energy": en,
        "scale": "1-10 (10 = best for mood/energy; 10 = worst for anxiety)",
        "emotion_tags": sorted(set(tags)),
        "note": None,
    })
# a few short notes on salient days
NOTES = {38: "Layoffs announced at work today. My team is on the list.", 39: "Couldn't sleep.",
         45: "Last day at the office next Friday.", 52: "Bad day. Stayed in bed until 2.",
         60: "Had a decent interview call!", 74: "Went to Jess's birthday dinner, actually enjoyed it."}
for c in mood:
    day_i = (date.fromisoformat(c["logged_at"][:10]) - START).days
    if day_i in NOTES:
        c["note"] = NOTES.pop(day_i)

# --- journal entries (2/week) with AI summaries ---
JOURNALS = {
 "baseline": [
  ("Started using the app this week because Dr. Ortiz suggested it. I don't really know what to write. Work was fine I guess. I keep waking up at 4 and my brain starts listing everything I've done wrong.",
   "Early-morning waking with ruminative self-criticism; ambivalent about journaling.", ["sleep", "rumination", "self_criticism"], -0.55),
  ("Everything feels like it takes three times the effort it should. I cancelled on Priya again tonight. I told her I had work but really I just couldn't face being 'on' for two hours. Then I sat on the couch scrolling until 1am which made me feel worse.",
   "Cancelled social plans due to low energy; late-night scrolling worsened mood.", ["social_withdrawal", "low_energy", "sleep"], -0.62),
  ("Session yesterday was about 'activity scheduling.' Picked a 20 minute walk in the mornings. Skeptical but I'll try.",
   "Agreed to morning walks as behavioral activation; skeptical but willing.", ["therapy", "behavioral_activation", "ambivalence"], 0.05),
  ("My mom called and asked why I sound tired all the time. I said I was busy. I don't want her to worry but I also feel like a fraud pretending.",
   "Concealing low mood from mother; feelings of inauthenticity.", ["family", "concealment", "guilt"], -0.48),
  ("Made it to the grocery store which felt like an accomplishment, which is kind of sad. Ate actual dinner instead of cereal.",
   "Completed grocery shopping and cooked dinner; small sense of accomplishment tinged with self-judgment.", ["self_care", "behavioral_activation", "self_criticism"], -0.15),
  ("Walked twice this week. The second time I noticed the light through the trees on Maple and for like a minute I wasn't thinking about anything. That's something.",
   "Completed two walks; brief moment of present-focused calm.", ["behavioral_activation", "nature", "mindfulness"], 0.28),
 ],
 "improving": [
  ("Lights out by 11:30 three nights in a row. Still waking up early but falling asleep is easier. Feel slightly less like a zombie at standups.",
   "Improved sleep onset with consistent bedtime; daytime functioning improving.", ["sleep", "routine", "work"], 0.35),
  ("Texted Priya and we got coffee Saturday. I almost bailed but didn't. It was really nice actually, she's going through stuff too.",
   "Followed through on social plan despite urge to cancel; felt connected.", ["social_connection", "avoidance_overcome"], 0.58),
  ("Noticed the 'I'm failing at everything' thought during a meeting and actually caught it. Wrote down evidence for and against like we practiced. It was mostly against.",
   "Applied cognitive restructuring to an all-or-nothing thought at work.", ["cognitive_restructuring", "work", "self_criticism"], 0.42),
  ("Good week. Not great, but good. I cooked twice and walked five days. My manager said my report was solid.",
   "Consistent routines and positive feedback at work; describes week as good.", ["routine", "work", "behavioral_activation"], 0.61),
  ("Went to the farmers market with my sister. Bought way too many peaches. I laughed a lot today.",
   "Enjoyable outing with sister; laughter and pleasure noted.", ["family", "pleasure", "social_connection"], 0.74),
  ("All hands meeting today. They announced a restructuring and my whole team is being cut. Severance is 8 weeks. I just sat in my car in the parking garage for 40 minutes. I don't know what I'm going to do about rent.",
   "Laid off in company restructuring; acute distress and financial worry.", ["job_loss", "financial_stress", "acute_stressor"], -0.78),
 ],
 "stressor_dip": [
  ("Can't stop doing the math on savings. Every time I close my eyes I see the number. Up until 3am again. Haven't walked since Thursday.",
   "Financial rumination driving insomnia; behavioral activation lapsed.", ["financial_stress", "rumination", "sleep", "practice_lapse"], -0.71),
  ("Told my mom. She was supportive but then started listing jobs her friends' kids have and I just shut down.",
   "Disclosed job loss to mother; felt overwhelmed by her problem-solving.", ["family", "job_loss", "overwhelm"], -0.44),
  ("I keep thinking I peaked and this is the beginning of everything falling apart. Some nights I think everyone would be fine without me around. I'm not going to do anything, I just notice the thought is there more than it used to be.",
   "Catastrophic thinking about the future; reports passive thoughts that others would be better off without her, denies intent.", ["hopelessness", "passive_ideation", "catastrophizing"], -0.86),
  ("Yesterday was my last day at work. Everyone was nice which almost made it worse. Today I slept 4 hours in the afternoon and now I'm wide awake.",
   "Final day at job; daytime oversleeping disrupting night sleep.", ["job_loss", "sleep", "grief"], -0.58),
  ("Told Dr. Ortiz about the thoughts. We made a safety plan and she moved my session up. I was scared she'd overreact but she didn't. I feel a little less alone with it.",
   "Disclosed passive ideation in session; collaborative safety plan created; felt supported.", ["therapy", "safety_planning", "support"], -0.12),
  ("Applied to two jobs. Walked around the block once. Small things. Priya brought over soup.",
   "Resumed job applications and brief walk; received support from friend.", ["behavioral_activation", "social_connection", "job_search"], 0.10),
 ],
 "recovery": [
  ("Back to walking most mornings. It's honestly the anchor of my day now that there's no commute. I put my phone in the kitchen at 11.",
   "Re-established morning walks and phone-free bedtime routine.", ["routine", "behavioral_activation", "sleep"], 0.45),
  ("Had a first round interview with a health tech company. I was nervous but it went well. Even if nothing comes of it I proved I can still do this.",
   "First interview went well; regained sense of competence.", ["job_search", "self_efficacy"], 0.62),
  ("Caught myself catastrophizing about money again but I used the worry window thing and it actually stayed contained to 15 minutes.",
   "Used scheduled worry time to contain financial rumination.", ["financial_stress", "coping_skill", "rumination"], 0.30),
  ("Jess's birthday. I didn't want to go, went anyway, stayed till 11. Danced a little. Who am I.",
   "Attended friend's birthday despite reluctance; enjoyed it.", ["social_connection", "avoidance_overcome", "pleasure"], 0.77),
  ("Second round interview Thursday. Sleeping 7 hours most nights. I don't feel 'fixed' but I feel like myself more days than not.",
   "Advancing in interview process; sleep consolidated; feels more like herself.", ["job_search", "sleep", "identity"], 0.66),
  ("Got an offer! Starting in three weeks. I cried in the kitchen and then called my mom. Want to keep the walks going when I start.",
   "Received job offer; plans to maintain routines after starting work.", ["job_search", "relief", "maintenance_planning"], 0.88),
 ],
}
journal = []
for ph, entries in JOURNALS.items():
    weeks = {"baseline": [0, 1, 2], "improving": [3, 4, 5], "stressor_dip": [6, 7, 8], "recovery": [9, 10, 11]}[ph]
    slots = [(w, off) for w in weeks for off in (2, 5)]  # Wed & Sat
    for (w, off), (text, summ, themes, sent) in zip(slots, entries):
        day = 7 * w + off
        if "restructuring" in text: day = STRESSOR_DAY  # Thursday of week 5
        journal.append({
            "entry_id": uid("jrn"),
            "created_at": ts(day, 22, random.randint(0, 50)),
            "text": text,
            "word_count": len(text.split()),
            "ai_summary": summ,
            "ai_themes": themes,
            "sentiment_score": sent,
            "sentiment_scale": "-1 (very negative) to +1 (very positive)",
            "shared_with_clinician": True,
        })
journal.sort(key=lambda x: x["created_at"])

# --- voice notes (1/week) ---
VOICE = [
 (0, "Okay, um, first voice note. I'm on the train. I feel kind of heavy today. Not anything specific, just heavy. Yeah. That's it.", "Diffuse heaviness without clear trigger.", -0.45),
 (1, "I did the walk this morning. It was raining a little and I almost didn't go. Glad I did I guess. Still tired.", "Completed walk despite rain; still fatigued.", 0.05),
 (2, "Just got out of a meeting where I felt totally stupid. My chest is tight. I'm going to try the naming-the-feeling thing. Embarrassed. Anxious. Okay, a little better.", "Work-triggered shame and anxiety; used affect labeling with some relief.", -0.25),
 (3, "Sunday reset. I meal prepped, which I haven't done in months. Feeling... proud? Weird word for chicken and rice.", "Meal prep completed; tentative pride.", 0.48),
 (4, "Saw my sister today. We walked by the river. It felt normal. Like old me.", "Pleasant time with sister; sense of returning to self.", 0.66),
 (5, "I can't, I can't really talk right now. They cut the whole team. I just wanted to say it out loud to something.", "Distressed immediately after layoff news.", -0.82),
 (6, "It's 3am. I can't sleep. Everything just keeps looping. I don't know why I'm recording this.", "Middle-of-night insomnia with looping thoughts.", -0.74),
 (7, "Didn't really get out of bed today. Ordered food. I know I should walk, I just... can't make my legs do it.", "Low activation; recognizes but cannot act on walking goal.", -0.70),
 (8, "Went around the block. Talked to Priya for an hour. Session tomorrow. Feeling a tiny bit more solid.", "Brief walk and supportive call; slightly more grounded.", 0.15),
 (9, "Interview prep. Nervous but in a normal way, not the drowning way. That distinction feels important.", "Normal anticipatory anxiety, distinguished from overwhelm.", 0.40),
 (10, "Morning walk, sun's out. Saw that same light on Maple Street. Remember noticing it in July? I feel a lot different now.", "Reflects on progress since July during walk.", 0.72),
 (11, "Offer accepted! Okay. I want to remember this feeling. And remember that the bad weeks ended.", "Accepted job offer; wants to remember that hard weeks pass.", 0.90),
]
voice = []
for w, transcript, summ, sent in VOICE:
    day = STRESSOR_DAY if w == 5 else 7 * w + random.choice([3, 4, 6])
    hour = 3 if w == 6 else random.choice([8, 12, 18, 19])
    words = len(transcript.split())
    voice.append({
        "voice_note_id": uid("vn"),
        "recorded_at": ts(day, hour, random.randint(0, 59)),
        "duration_sec": int(words / 2.2 + random.randint(3, 12)),
        "audio_uri": f"s3://carelinq-demo/audio/{PATIENT_ID}/vn_w{w:02d}.m4a",
        "transcript": transcript,
        "transcription_confidence": round(random.uniform(0.88, 0.97), 2),
        "ai_summary": summ,
        "sentiment_score": sent,
        "shared_with_clinician": True,
    })

# --- practices (habits) ---
PRACTICES = [
    {"practice_id": "prc_walk", "name": "Morning walk (20 min)", "track": "make_it_happen", "target_per_week": 5, "created_at": ts(8, 18, 30)},
    {"practice_id": "prc_bed", "name": "Lights out by 11:30pm", "track": "make_it_happen", "target_per_week": 5, "created_at": ts(8, 18, 31)},
    {"practice_id": "prc_reach", "name": "Text or call a friend", "track": "make_it_happen", "target_per_week": 2, "created_at": ts(8, 18, 32)},
    {"practice_id": "prc_med", "name": "Take sertraline", "track": "make_it_happen", "target_per_week": 7, "created_at": ts(8, 18, 33)},
    {"practice_id": "prc_name", "name": "Pause and name the feeling", "track": "meet_the_moment", "target_per_week": None,
     "trigger": "When I notice a surge of shame or anxiety", "created_at": ts(8, 18, 34)},
]
def p_done(pid, i):
    hv = h(i)
    base = {"prc_walk": 0.28 + 0.65 * hv, "prc_bed": 0.20 + 0.70 * hv, "prc_reach": 0.08 + 0.30 * hv, "prc_med": 0.82 + 0.17 * hv}[pid]
    return random.random() < base
practice_logs = []
for i in range(8, DAYS):
    for p in PRACTICES[:4]:
        practice_logs.append({
            "log_id": uid("plog"), "practice_id": p["practice_id"], "date": str(d(i)),
            "completed": p_done(p["practice_id"], i),
        })
weekly_cycles = []
for w in range(1, 12):
    for p in PRACTICES[:4]:
        done = sum(1 for l in practice_logs if l["practice_id"] == p["practice_id"] and l["completed"]
                   and 7 * w <= (date.fromisoformat(l["date"]) - START).days < 7 * w + 7)
        weekly_cycles.append({"practice_id": p["practice_id"], "week": w, "cycle_start": str(d(7 * w)),
                              "cycle_end": str(d(7 * w + 6)), "target": p["target_per_week"], "completed": done,
                              "met_target": done >= p["target_per_week"]})

SITUATIONS = [
    ("Manager questioned my numbers in front of the team", "embarrassed"),
    ("Saw a former coworker's LinkedIn post about a new job", "envious"),
    ("Checked bank balance", "anxious"),
    ("Mom asked about job search again", "irritated"),
    ("Woke at 4am with racing thoughts", "dread"),
    ("Recruiter didn't reply after a week", "discouraged"),
    ("Saw friends' group photo I wasn't in", "lonely"),
    ("Long queue at pharmacy, felt trapped", "overwhelmed"),
]
mtm = []
for i in range(7, DAYS):
    rate = 0.35 if phase(i) == "stressor_dip" else 0.22
    if random.random() < rate:
        sit, emo = random.choice(SITUATIONS[1:6] if i >= STRESSOR_DAY else SITUATIONS[:1] + SITUATIONS[4:])
        before = clamp(round(8.5 - 3 * h(i) + random.gauss(0, 0.8)), 3, 10)
        mtm.append({
            "log_id": uid("mtm"), "practice_id": "prc_name", "logged_at": ts(i, random.randint(9, 22), random.randint(0, 59)),
            "situation": sit, "emotion_named": emo,
            "intensity_before": before, "intensity_after": clamp(before - random.choice([1, 2, 2, 3]), 1, 10),
            "scale": "0-10 subjective distress",
        })

self_report = {
    "_synthetic": True,
    "patient_id": PATIENT_ID,
    "phq9_responses": phq9,
    "mood_checkins": mood,
    "journal_entries": journal,
    "voice_notes": voice,
    "practices": {"definitions": PRACTICES, "daily_logs": practice_logs, "weekly_cycles": weekly_cycles,
                  "meet_the_moment_logs": mtm},
}

# =====================================================================
# healthkit.json
# =====================================================================
def lerp(lo, hi, i, sd): return lo + (hi - lo) * h(i) + random.gauss(0, sd)
sleep_sessions, daily = [], []
for i in range(DAYS):
    watch_worn = random.random() > 0.06
    # sleep night of day i -> morning of day i+1
    if watch_worn and i < DAYS - 1:
        asleep_min = clamp(lerp(345, 440, i, 30), 220, 560)
        if STRESSOR_DAY <= i <= 52: asleep_min -= random.uniform(10, 45)
        bedtime_offset_min = clamp(lerp(55, -45, i, 25), -90, 150)  # minutes after midnight (negative = before)
        latency = clamp(lerp(42, 12, i, 7), 3, 90)
        awake_min = clamp(lerp(48, 14, i, 8), 3, 120)
        awakenings = int(clamp(round(lerp(5, 1.5, i, 1)), 0, 10))
        deep = asleep_min * clamp(random.gauss(0.11 + 0.04 * h(i), 0.015), 0.06, 0.2)
        rem = asleep_min * clamp(random.gauss(0.19 + 0.04 * h(i), 0.02), 0.12, 0.28)
        core = asleep_min - deep - rem
        in_bed_start = datetime.combine(d(i + 1), time(0, 0)) + timedelta(minutes=bedtime_offset_min)
        in_bed_end = in_bed_start + timedelta(minutes=latency + asleep_min + awake_min)
        sleep_sessions.append({
            "night_of": str(d(i)),
            "hk_type": "HKCategoryTypeIdentifierSleepAnalysis",
            "source": "Apple Watch",
            "in_bed_start": in_bed_start.strftime("%Y-%m-%dT%H:%M:%S") + TZ,
            "in_bed_end": in_bed_end.strftime("%Y-%m-%dT%H:%M:%S") + TZ,
            "sleep_onset_latency_min": round(latency),
            "total_asleep_min": round(asleep_min),
            "awake_min": round(awake_min),
            "awakenings": awakenings,
            "stages_min": {"asleepCore": round(core), "asleepDeep": round(deep), "asleepREM": round(rem), "awake": round(awake_min)},
            "sleep_efficiency": round(asleep_min / (latency + asleep_min + awake_min), 3),
        })
    steps = max(400, int(lerp(3600, 8900, i, 900) * (0.75 if STRESSOR_DAY <= i <= 54 else 1)))
    ex = max(0, round(lerp(6, 32, i, 6)))
    daily.append({
        "date": str(d(i)),
        "watch_worn": watch_worn,
        "HKQuantityTypeIdentifierStepCount": {"value": steps, "unit": "count", "source": "iPhone+Watch"},
        "HKQuantityTypeIdentifierActiveEnergyBurned": {"value": round(steps * 0.038 + ex * 6.5 + random.gauss(40, 20)), "unit": "kcal"},
        "HKQuantityTypeIdentifierAppleExerciseTime": {"value": ex if watch_worn else None, "unit": "min"},
        "HKQuantityTypeIdentifierRestingHeartRate": {"value": round(lerp(73, 63, i, 1.6)) if watch_worn else None, "unit": "count/min"},
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": {"value": round(clamp(lerp(29, 47, i, 4.5), 12, 90), 1) if watch_worn else None,
                                                            "unit": "ms", "aggregation": "daily_mean_of_samples"},
        "HKQuantityTypeIdentifierRespiratoryRate": {"value": round(lerp(16.2, 14.6, i, 0.4), 1) if watch_worn else None,
                                                    "unit": "count/min", "aggregation": "sleep_mean"},
        "HKQuantityTypeIdentifierTimeInDaylight": {"value": max(0, round(lerp(22, 68, i, 10))) if watch_worn else None, "unit": "min"},
        "HKCategoryTypeIdentifierMindfulSession": {"value": (random.choice([3, 5, 10]) if random.random() < 0.15 + 0.4 * h(i) else 0), "unit": "min"},
    })

healthkit = {
    "_synthetic": True,
    "patient_id": PATIENT_ID,
    "sleep_sessions": sleep_sessions,
    "daily_metrics": daily,
}

for name, obj in [("patient.json", patient), ("self_report.json", self_report), ("healthkit.json", healthkit)]:
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
print("ok", len(phq9), len(mood), len(journal), len(voice), len(practice_logs), len(mtm), len(sleep_sessions), len(daily))
