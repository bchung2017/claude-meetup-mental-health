# Per-patient schema model

One row in `patients` owns every other row through `patient_id`. The model is a straight
normalization of the CareLinq bundle (`data/sample/README.md`): three source files become
twelve tables. DDL lives in `app/schema.sql` and is identical for SQLite and Postgres.

Conventions:

- Timestamps are ISO 8601 text with offset (`2026-08-20T22:18:00-04:00`); dates are `YYYY-MM-DD`.
  Both sort lexically, so `ORDER BY` works without parsing.
- Booleans are `INTEGER` 0/1.
- Nested objects the dashboard never filters on are stored as JSON text and decoded by the API.
- Natural keys from the source (`checkin_id`, `entry_id`, …) are the primary keys. Tables without
  a source id use a composite key on `(patient_id, <natural unit>)`.
- `patient_id` is on every table so a single predicate scopes any query to one patient.

## Entity-relationship diagram

```mermaid
erDiagram
    patients ||--o{ sessions : "has"
    patients ||--o{ phq9_responses : "completes weekly"
    patients ||--o{ mood_checkins : "logs daily"
    patients ||--o{ journal_entries : "writes"
    patients ||--o{ voice_notes : "records"
    patients ||--o{ practices : "commits to"
    practices ||--o{ practice_daily_logs : "completed?"
    practices ||--o{ practice_weekly_cycles : "weekly rollup"
    practices ||--o{ meet_the_moment_logs : "event-triggered"
    patients ||--o{ sleep_sessions : "nightly"
    patients ||--o{ daily_metrics : "daily"

    patients {
        text patient_id PK
        text display_name
        text date_of_birth
        text sex_at_birth
        text pronouns
        text timezone
        json enrollment
        json clinical
        json care_team
    }
    sessions {
        text session_id PK
        text patient_id FK
        int session_number
        text scheduled_start
        int duration_min
        text modality
        text cpt_code
        int attended
    }
    phq9_responses {
        text response_id PK
        text patient_id FK
        int administration_week
        text completed_at
        json items
        int total_score
        int item9_score
        text severity_band
        text functional_difficulty
    }
    mood_checkins {
        text checkin_id PK
        text patient_id FK
        text logged_at
        int mood
        int anxiety
        int energy
        json emotion_tags
        text note
    }
    journal_entries {
        text entry_id PK
        text patient_id FK
        text created_at
        text text
        int word_count
        text ai_summary
        json ai_themes
        real sentiment_score
        int shared_with_clinician
    }
    voice_notes {
        text voice_note_id PK
        text patient_id FK
        text recorded_at
        int duration_sec
        text audio_uri
        text transcript
        real transcription_confidence
        text ai_summary
        real sentiment_score
        int shared_with_clinician
    }
    practices {
        text patient_id PK_FK
        text practice_id PK
        text name
        text track
        int target_per_week
        text trigger_text
        text created_at
    }
    practice_daily_logs {
        text log_id PK
        text patient_id FK
        text practice_id FK
        text date
        int completed
    }
    practice_weekly_cycles {
        text patient_id PK_FK
        text practice_id PK_FK
        int week PK
        text cycle_start
        text cycle_end
        int target
        int completed
        int met_target
    }
    meet_the_moment_logs {
        text log_id PK
        text patient_id FK
        text practice_id FK
        text logged_at
        text situation
        text emotion_named
        int intensity_before
        int intensity_after
    }
    sleep_sessions {
        text patient_id PK_FK
        text night_of PK
        text source
        text in_bed_start
        text in_bed_end
        int sleep_onset_latency_min
        int total_asleep_min
        int awake_min
        int awakenings
        int asleep_core_min
        int asleep_deep_min
        int asleep_rem_min
        real sleep_efficiency
    }
    daily_metrics {
        text patient_id PK_FK
        text date PK
        int watch_worn
        int step_count
        int active_energy_kcal
        int exercise_min
        int resting_hr
        real hrv_sdnn_ms
        real respiratory_rate
        int time_in_daylight_min
        int mindful_min
    }
```

## Tables

### `patients` ← `patient.json`

| Column | Type | Notes |
|---|---|---|
| `patient_id` | TEXT PK | `pt_…` |
| `display_name`, `date_of_birth`, `sex_at_birth`, `pronouns`, `timezone` | TEXT | |
| `enrollment` | JSON | `{enrolled_at, program, observation_window{start,end}, practices_start, consents{…}, devices[]}` |
| `clinical` | JSON | `{primary_diagnosis{icd10,description}, secondary_diagnoses[], medications[], treatment_modality, intake_phq9_total}` |
| `care_team` | JSON | `[{clinician_id, name, role}]` |

### `sessions` ← `patient.json → sessions[]`

| Column | Type | Notes |
|---|---|---|
| `session_id` | TEXT PK | `ses_01` … |
| `patient_id` | TEXT FK | |
| `session_number` | INTEGER | 1-based |
| `scheduled_start` | TEXT | Tuesdays 17:00 in the sample; between-session window = this → next `scheduled_start` |
| `duration_min` | INTEGER | |
| `modality` | TEXT | `in_person` \| `telehealth` |
| `cpt_code` | TEXT | `90791` intake, `90837` thereafter |
| `attended` | INTEGER | 0/1 |

### `phq9_responses` ← `self_report.json → phq9_responses[]`

| Column | Type | Notes |
|---|---|---|
| `response_id` | TEXT PK | |
| `patient_id` | TEXT FK | |
| `administration_week` | INTEGER | 0–11 |
| `completed_at` | TEXT | |
| `items` | JSON | `[{item 1–9, text, score 0–3}]` |
| `total_score` | INTEGER | 0–27 |
| `item9_score` | INTEGER | denormalized from `items`; `> 0` is the safety alert |
| `severity_band` | TEXT | minimal \| mild \| moderate \| moderately_severe \| severe |
| `functional_difficulty` | TEXT | not_difficult_at_all \| somewhat_difficult \| very_difficult \| extremely_difficult |

### `mood_checkins` ← `self_report.json → mood_checkins[]`

| Column | Type | Notes |
|---|---|---|
| `checkin_id` | TEXT PK | |
| `patient_id` | TEXT FK | |
| `logged_at` | TEXT | |
| `mood` | INTEGER | 1–10, 10 best |
| `anxiety` | INTEGER | 1–10, 10 worst |
| `energy` | INTEGER | 1–10, 10 best |
| `emotion_tags` | JSON | `["drained", "dread", …]` |
| `note` | TEXT NULL | |

### `journal_entries` ← `self_report.json → journal_entries[]`

| Column | Type | Notes |
|---|---|---|
| `entry_id` | TEXT PK | |
| `patient_id` | TEXT FK | |
| `created_at` | TEXT | |
| `text` | TEXT | free text |
| `word_count` | INTEGER | |
| `ai_summary` | TEXT | |
| `ai_themes` | JSON | snake_case tags; `passive_ideation` is the risk-language flag |
| `sentiment_score` | REAL | -1 … +1 |
| `shared_with_clinician` | INTEGER | 0/1 |

### `voice_notes` ← `self_report.json → voice_notes[]`

| Column | Type | Notes |
|---|---|---|
| `voice_note_id` | TEXT PK | |
| `patient_id` | TEXT FK | |
| `recorded_at` | TEXT | |
| `duration_sec` | INTEGER | |
| `audio_uri` | TEXT | placeholder S3 path |
| `transcript` | TEXT | |
| `transcription_confidence` | REAL | 0–1 |
| `ai_summary` | TEXT | |
| `sentiment_score` | REAL | -1 … +1 |
| `shared_with_clinician` | INTEGER | 0/1 |

### `practices` ← `self_report.json → practices.definitions[]`

| Column | Type | Notes |
|---|---|---|
| `patient_id` | TEXT PK/FK | |
| `practice_id` | TEXT PK | `prc_walk` … unique per patient, not globally |
| `name` | TEXT | |
| `track` | TEXT | `make_it_happen` (weekly target) \| `meet_the_moment` (event-triggered) |
| `target_per_week` | INTEGER NULL | NULL for `meet_the_moment` |
| `trigger_text` | TEXT NULL | source field is `trigger`; renamed to avoid the SQL keyword |
| `created_at` | TEXT | |

### `practice_daily_logs` ← `practices.daily_logs[]`

| Column | Type | Notes |
|---|---|---|
| `log_id` | TEXT PK | |
| `patient_id`, `practice_id` | TEXT FK | |
| `date` | TEXT | one row per make_it_happen practice per day |
| `completed` | INTEGER | 0/1 |

### `practice_weekly_cycles` ← `practices.weekly_cycles[]`

| Column | Type | Notes |
|---|---|---|
| `patient_id`, `practice_id`, `week` | PK | Monday–Sunday rollup; recomputable from daily logs |
| `cycle_start`, `cycle_end` | TEXT | |
| `target`, `completed` | INTEGER | |
| `met_target` | INTEGER | 0/1 |

### `meet_the_moment_logs` ← `practices.meet_the_moment_logs[]`

| Column | Type | Notes |
|---|---|---|
| `log_id` | TEXT PK | |
| `patient_id`, `practice_id` | TEXT FK | |
| `logged_at` | TEXT | |
| `situation`, `emotion_named` | TEXT | |
| `intensity_before`, `intensity_after` | INTEGER | 0–10 subjective distress |

### `sleep_sessions` ← `healthkit.json → sleep_sessions[]`

One row per night the watch was worn. `stages_min` is flattened.

| Column | Type | Notes |
|---|---|---|
| `patient_id`, `night_of` | PK | `night_of` is the evening the night started |
| `source` | TEXT | `Apple Watch` |
| `in_bed_start`, `in_bed_end` | TEXT | |
| `sleep_onset_latency_min`, `total_asleep_min`, `awake_min` | INTEGER | |
| `awakenings` | INTEGER | |
| `asleep_core_min`, `asleep_deep_min`, `asleep_rem_min` | INTEGER | from `stages_min`; `awake` duplicates `awake_min` and is dropped |
| `sleep_efficiency` | REAL | asleep / time in bed |

### `daily_metrics` ← `healthkit.json → daily_metrics[]`

One row per day. HealthKit identifiers map to columns; watch-only metrics are NULL when
`watch_worn = 0`. Units are fixed per column and not stored.

| Column | HealthKit identifier | Unit | Nullable |
|---|---|---|---|
| `patient_id`, `date` | — | PK | |
| `watch_worn` | — | 0/1 | |
| `step_count` | `HKQuantityTypeIdentifierStepCount` | count | no |
| `active_energy_kcal` | `HKQuantityTypeIdentifierActiveEnergyBurned` | kcal | no |
| `exercise_min` | `HKQuantityTypeIdentifierAppleExerciseTime` | min | watch |
| `resting_hr` | `HKQuantityTypeIdentifierRestingHeartRate` | count/min | watch |
| `hrv_sdnn_ms` | `HKQuantityTypeIdentifierHeartRateVariabilitySDNN` | ms, daily mean | watch |
| `respiratory_rate` | `HKQuantityTypeIdentifierRespiratoryRate` | count/min, sleep mean | watch |
| `time_in_daylight_min` | `HKQuantityTypeIdentifierTimeInDaylight` | min | watch |
| `mindful_min` | `HKCategoryTypeIdentifierMindfulSession` | min | no |

## Queries the README's test cases reduce to

```sql
-- 1. PHQ-9 item 9 safety flag
SELECT completed_at, total_score FROM phq9_responses
 WHERE patient_id = ? AND item9_score > 0;

-- 2. Reliable deterioration: +5 vs prior low
SELECT a.administration_week, a.total_score
  FROM phq9_responses a
 WHERE a.patient_id = ?
   AND a.total_score - (SELECT MIN(b.total_score) FROM phq9_responses b
                         WHERE b.patient_id = a.patient_id
                           AND b.administration_week < a.administration_week) >= 5;

-- 5. Risk language in free text (ai_themes is JSON text; LIKE is enough at this scale)
SELECT created_at, ai_summary FROM journal_entries
 WHERE patient_id = ? AND ai_themes LIKE '%passive_ideation%';

-- 6. Engagement: check-ins per ISO week
SELECT substr(logged_at, 1, 10) AS day, COUNT(*) FROM mood_checkins
 WHERE patient_id = ? GROUP BY 1;

-- 7. Sleep: 7-night rolling mean needs a window function (Postgres) or app code (SQLite 3.25+ has windows)
SELECT night_of, AVG(total_asleep_min) OVER (ORDER BY night_of ROWS 6 PRECEDING) AS asleep_7n
  FROM sleep_sessions WHERE patient_id = ?;
```

## Not modeled

- Foreign keys are implied, not declared. Both backends accept the DDL as-is; declaring them
  would force insert ordering and gain nothing while the importer is the only writer.
- Patient-level fields inside `enrollment` / `clinical` / `care_team` stay JSON. Promote a field
  to a column when a query needs to filter or join on it.
- `scale` strings on `mood_checkins` and `meet_the_moment_logs` are dropped; the scale is fixed
  and documented above.
