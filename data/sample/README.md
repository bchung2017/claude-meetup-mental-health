# CareLinq synthetic patient: dashboard test data

**Everything here is fictional.** One synthetic patient ("Maya R.", `pt_7f3a9c21`), 12 weeks of between-session data, Mon 2026-07-13 → Sun 2026-10-04. All timestamps are ISO 8601 with offset `-04:00` (America/New_York, EDT). Every file carries `"_synthetic": true`.

Regenerate with `python3 generate.py` (seeded, so output is identical each run). Change `random.seed(42)` for a different but same-shaped patient.

| File | What it holds |
|---|---|
| `patient.json` | Demographics, diagnoses, meds, care team, consents, devices, 12 therapy sessions |
| `self_report.json` | PHQ-9, daily mood check-ins, journal entries, voice notes, practices (habits) |
| `healthkit.json` | Nightly sleep sessions + daily activity/vitals, keyed by Apple HealthKit identifiers |
| `generate.py` | The generator |

Join key across files: `patient_id`. Join to sessions by timestamp: sessions are Tuesdays 17:00, so "between-session window" = Tue 18:00 → next Tue 17:00.

---

## The clinical story (ground truth)

| Weeks | Phase | What happens |
|---|---|---|
| 0–2 | Baseline | Moderately severe depression, insomnia (late bedtime, early waking), social withdrawal. Week 0 is an enrollment buffer; practices start week 1. |
| 3–5 | Improving | Walks and earlier bedtime take hold; PHQ-9 18 → 10. |
| 5 (Thu Aug 20) | **Stressor** | Laid off in a company restructuring. Journal + voice note same day. |
| 6–8 | Dip | Sleep, steps, HRV, mood, check-in adherence all drop. **PHQ-9 week 7 = 16 with item 9 = 1.** Journal (Sep 2) describes passive ideation, denies intent. Next journal (Sep 9) reports a safety plan made with the therapist. |
| 9–11 | Recovery | Routines resume, interviews, job offer. PHQ-9 ends at 7 (mild). |

The same latent wellbeing curve drives every stream, so self-report and physiology move together (with realistic noise and lag).

### Expected dashboard behaviors (use as test cases)

| # | Signal | Where | Should fire? |
|---|---|---|---|
| 1 | **PHQ-9 item 9 > 0** (safety) | `phq9_responses[week=7]`, 2026-08-31 | Yes, highest priority |
| 2 | Reliable deterioration (Δ ≥ +5 vs. prior low) | PHQ-9 10 (wk 5) → 16 (wk 7) | Yes |
| 3 | Severity band worsens | moderate → moderately_severe, wk 7 | Yes |
| 4 | Reliable improvement + response (≥ 50% drop from baseline) | 18 → 7 by wk 11 | Yes, positive flag |
| 5 | Risk language in free text | Journal 2026-09-02 (`ai_themes` includes `passive_ideation`) | Yes, if you run NLP over text |
| 6 | Engagement drop | Mood check-ins fall from ~7/wk to 4–5/wk in wks 6–7; walk practice 0/5 in wk 7 | Yes |
| 7 | Sleep decline | 7-day mean asleep drops ~50 min wk 4 → wk 7; bedtime drifts past 00:30 | Yes |
| 8 | Missing watch data | ~6% of days have `watch_worn: false` (nulls for watch-only metrics, no sleep session) | Handle gracefully, don't alert |

Note on item 9: in a real deployment this needs a defined clinical response protocol, not only a dashboard badge. Worth showing in the demo as a distinct, unmissable alert tier.

---

## `patient.json`

```
patient_id, display_name, date_of_birth, sex_at_birth, pronouns, timezone
enrollment:
  enrolled_at, program, observation_window{start,end}, practices_start
  consents{ self_report_sharing, healthkit_sharing, healthkit_types_authorized[], journal_ai_summary, voice_note_transcription }
  devices[]{ type, model, os }
clinical: primary_diagnosis{icd10,description}, secondary_diagnoses[], medications[], treatment_modality, intake_phq9_total
care_team[]{ clinician_id, name, role }
sessions[]{ session_id, session_number, scheduled_start, duration_min, modality, cpt_code, attended }
```

## `self_report.json`

### `phq9_responses[]` (weekly, Monday evening before session; 12 records)
```
response_id, instrument="PHQ-9", administration_week (0–11), completed_at
items[]{ item 1–9, text, score 0–3 }
total_score 0–27
severity_band: minimal (0–4) | mild (5–9) | moderate (10–14) | moderately_severe (15–19) | severe (20–27)
functional_difficulty: not_difficult_at_all | somewhat_difficult | very_difficult | extremely_difficult
```
Totals by week: 18, 17, 15, 13, 11, 10, 13, 16, 14, 12, 9, 7.

### `mood_checkins[]` (daily, with realistic gaps; ~72 records)
```
checkin_id, logged_at
mood 1–10 (10 best), anxiety 1–10 (10 worst), energy 1–10 (10 best)
emotion_tags[]  – granular labels, e.g. "drained", "dread", "hopeful", "connected"
note            – null except on a few salient days
```

### `journal_entries[]` (2/week, Wed & Sat; 24 records)
```
entry_id, created_at, text, word_count
ai_summary        – one-line summary as an LLM would produce for the clinician
ai_themes[]       – snake_case tags (sleep, rumination, job_loss, passive_ideation, …)
sentiment_score   – -1 to +1
shared_with_clinician
```

### `voice_notes[]` (1/week; 12 records)
```
voice_note_id, recorded_at, duration_sec
audio_uri          – placeholder S3 path, no real audio
transcript, transcription_confidence, ai_summary, sentiment_score, shared_with_clinician
```

### `practices`
- `definitions[]`: 5 practices. Four on the **make_it_happen** track with a weekly target (walk 5, lights-out 5, reach out 2, medication 7); one on the **meet_the_moment** track (event-triggered, no target).
- `daily_logs[]`: `{log_id, practice_id, date, completed}` per make_it_happen practice per day, from week 1.
- `weekly_cycles[]`: Monday–Sunday rollups `{practice_id, week, cycle_start, cycle_end, target, completed, met_target}`. Precomputed for convenience; you can recompute from `daily_logs`.
- `meet_the_moment_logs[]`: `{log_id, practice_id, logged_at, situation, emotion_named, intensity_before, intensity_after}` on a 0–10 distress scale.

## `healthkit.json`

Field names use Apple HealthKit type identifiers and units so the ingestion path matches what a real HealthKit export would give you. Values are **daily aggregates**, not raw samples.

### `sleep_sessions[]` (one per night when watch was worn)
```
night_of            – the evening date the night started
hk_type             = HKCategoryTypeIdentifierSleepAnalysis
in_bed_start, in_bed_end
sleep_onset_latency_min, total_asleep_min, awake_min, awakenings
stages_min{ asleepCore, asleepDeep, asleepREM, awake }   – HealthKit sleep stage names
sleep_efficiency    – asleep / time in bed
```

### `daily_metrics[]` (84 records, one per day)
Each metric is `{ value, unit, … }`; `value` is `null` when `watch_worn` is false and the metric needs the watch.

| Key | Unit | Notes |
|---|---|---|
| `HKQuantityTypeIdentifierStepCount` | count | iPhone + Watch, never null |
| `HKQuantityTypeIdentifierActiveEnergyBurned` | kcal | |
| `HKQuantityTypeIdentifierAppleExerciseTime` | min | |
| `HKQuantityTypeIdentifierRestingHeartRate` | count/min | ~73 → 63 over the arc, rises in dip |
| `HKQuantityTypeIdentifierHeartRateVariabilitySDNN` | ms | daily mean; ~29 → 47, drops in dip |
| `HKQuantityTypeIdentifierRespiratoryRate` | count/min | sleep mean |
| `HKQuantityTypeIdentifierTimeInDaylight` | min | |
| `HKCategoryTypeIdentifierMindfulSession` | min | 0 on most days |

---

## Suggested dashboard views

1. **Roster card**: latest PHQ-9 + band, trend arrow, active alert count, days since last check-in.
2. **Trajectory**: PHQ-9 totals (weekly) over a daily mood line, session dates as vertical markers, stressor annotation.
3. **Between-session digest**: for the window since last session, AI summaries of journals/voice notes, practice completion vs. target, sleep/HRV deltas vs. the patient's own 4-week baseline.
4. **Body–mind overlay**: sleep minutes, HRV, steps alongside mood, to show the dip co-moving across streams.
