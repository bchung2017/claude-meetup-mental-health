CREATE TABLE IF NOT EXISTS entries (
  id         TEXT PRIMARY KEY,
  created_at BIGINT  NOT NULL,
  depression INTEGER NOT NULL,
  adhd       INTEGER NOT NULL,
  note       TEXT    NOT NULL
);

-- Per-patient model (CareLinq streams; see data/sample/README.md). Join key: patient_id.
-- Timestamps are ISO 8601 strings with offset; dates are YYYY-MM-DD. Nested objects are JSON text.

CREATE TABLE IF NOT EXISTS patients (
  patient_id     TEXT PRIMARY KEY,
  display_name   TEXT NOT NULL,
  date_of_birth  TEXT NOT NULL,
  sex_at_birth   TEXT NOT NULL,
  pronouns       TEXT NOT NULL,
  timezone       TEXT NOT NULL,
  enrollment     TEXT NOT NULL,
  clinical       TEXT NOT NULL,
  care_team      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id      TEXT PRIMARY KEY,
  patient_id      TEXT NOT NULL,
  session_number  INTEGER NOT NULL,
  scheduled_start TEXT NOT NULL,
  duration_min    INTEGER NOT NULL,
  modality        TEXT NOT NULL,
  cpt_code        TEXT NOT NULL,
  attended        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS phq9_responses (
  response_id           TEXT PRIMARY KEY,
  patient_id            TEXT NOT NULL,
  administration_week   INTEGER NOT NULL,
  completed_at          TEXT NOT NULL,
  items                 TEXT NOT NULL,
  total_score           INTEGER NOT NULL,
  item9_score           INTEGER NOT NULL,
  severity_band         TEXT NOT NULL,
  functional_difficulty TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mood_checkins (
  checkin_id   TEXT PRIMARY KEY,
  patient_id   TEXT NOT NULL,
  logged_at    TEXT NOT NULL,
  mood         INTEGER NOT NULL,
  anxiety      INTEGER NOT NULL,
  energy       INTEGER NOT NULL,
  emotion_tags TEXT NOT NULL,
  note         TEXT
);

CREATE TABLE IF NOT EXISTS journal_entries (
  entry_id              TEXT PRIMARY KEY,
  patient_id            TEXT NOT NULL,
  created_at            TEXT NOT NULL,
  text                  TEXT NOT NULL,
  word_count            INTEGER NOT NULL,
  ai_summary            TEXT NOT NULL,
  ai_themes             TEXT NOT NULL,
  sentiment_score       REAL NOT NULL,
  shared_with_clinician INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS voice_notes (
  voice_note_id            TEXT PRIMARY KEY,
  patient_id               TEXT NOT NULL,
  recorded_at              TEXT NOT NULL,
  duration_sec             INTEGER NOT NULL,
  audio_uri                TEXT NOT NULL,
  transcript               TEXT NOT NULL,
  transcription_confidence REAL NOT NULL,
  ai_summary               TEXT NOT NULL,
  sentiment_score          REAL NOT NULL,
  shared_with_clinician    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS practices (
  patient_id      TEXT NOT NULL,
  practice_id     TEXT NOT NULL,
  name            TEXT NOT NULL,
  track           TEXT NOT NULL,
  target_per_week INTEGER,
  trigger_text    TEXT,
  created_at      TEXT NOT NULL,
  PRIMARY KEY (patient_id, practice_id)
);

CREATE TABLE IF NOT EXISTS practice_daily_logs (
  log_id      TEXT PRIMARY KEY,
  patient_id  TEXT NOT NULL,
  practice_id TEXT NOT NULL,
  date        TEXT NOT NULL,
  completed   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS practice_weekly_cycles (
  patient_id  TEXT NOT NULL,
  practice_id TEXT NOT NULL,
  week        INTEGER NOT NULL,
  cycle_start TEXT NOT NULL,
  cycle_end   TEXT NOT NULL,
  target      INTEGER NOT NULL,
  completed   INTEGER NOT NULL,
  met_target  INTEGER NOT NULL,
  PRIMARY KEY (patient_id, practice_id, week)
);

CREATE TABLE IF NOT EXISTS meet_the_moment_logs (
  log_id           TEXT PRIMARY KEY,
  patient_id       TEXT NOT NULL,
  practice_id      TEXT NOT NULL,
  logged_at        TEXT NOT NULL,
  situation        TEXT NOT NULL,
  emotion_named    TEXT NOT NULL,
  intensity_before INTEGER NOT NULL,
  intensity_after  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sleep_sessions (
  patient_id              TEXT NOT NULL,
  night_of                TEXT NOT NULL,
  source                  TEXT NOT NULL,
  in_bed_start            TEXT NOT NULL,
  in_bed_end              TEXT NOT NULL,
  sleep_onset_latency_min INTEGER NOT NULL,
  total_asleep_min        INTEGER NOT NULL,
  awake_min               INTEGER NOT NULL,
  awakenings              INTEGER NOT NULL,
  asleep_core_min         INTEGER NOT NULL,
  asleep_deep_min         INTEGER NOT NULL,
  asleep_rem_min          INTEGER NOT NULL,
  sleep_efficiency        REAL NOT NULL,
  PRIMARY KEY (patient_id, night_of)
);

-- One row per day. Watch-only metrics are NULL when watch_worn = 0.
CREATE TABLE IF NOT EXISTS daily_metrics (
  patient_id            TEXT NOT NULL,
  date                  TEXT NOT NULL,
  watch_worn            INTEGER NOT NULL,
  step_count            INTEGER NOT NULL,
  active_energy_kcal    INTEGER NOT NULL,
  exercise_min          INTEGER,
  resting_hr            INTEGER,
  hrv_sdnn_ms           REAL,
  respiratory_rate      REAL,
  time_in_daylight_min  INTEGER,
  mindful_min           INTEGER NOT NULL,
  PRIMARY KEY (patient_id, date)
);
