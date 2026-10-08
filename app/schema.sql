-- Single-person tracker (pre-dates the per-patient model; kept as-is).
CREATE TABLE IF NOT EXISTS entries (
  id         TEXT PRIMARY KEY,
  created_at BIGINT  NOT NULL,
  depression INTEGER NOT NULL,
  adhd       INTEGER NOT NULL,
  meds_taken INTEGER NOT NULL DEFAULT 0,
  note       TEXT    NOT NULL
);

-- Everything below is the integrated per-patient schema (docs/integrated-patient-schema.md),
-- made idempotent so it is applied on every startup: IF NOT EXISTS on tables and indexes,
-- views dropped and recreated, reference rows ON CONFLICT DO NOTHING.

-- ============================================================================
-- Integrated per-patient schema
-- Sources: CareLinq bundle (patient.json, self_report.json, healthkit.json)
--          Behavidence Enhanced Clinical RTM Report (PDF)
--
-- Dialect: the common subset of SQLite and PostgreSQL. TEXT / INTEGER / REAL
-- only; no JSONB, ENUM, SERIAL or dialect date functions. Timestamps are
-- ISO 8601 text with offset, dates are YYYY-MM-DD; both sort lexically.
-- Booleans are INTEGER 0/1.
--
-- Foreign keys are DECLARED (the previous model left them implied). SQLite
-- does not enforce them unless `PRAGMA foreign_keys = ON`, so they act as
-- documentation there and as real constraints on Postgres. Insert in the
-- order tables appear in this file.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. PROVENANCE
-- Every clinical fact points at the artifact it came from. This is what lets
-- two sources disagree without either one being silently overwritten.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS data_sources (
    source_id        TEXT PRIMARY KEY,         -- 'src_carelinq_patient', 'src_behavidence_rtm'
    kind             TEXT NOT NULL             -- json_bundle | clinical_pdf | ehr_export | device_sync
                     CHECK (kind IN ('json_bundle','clinical_pdf','ehr_export','device_sync')),
    label            TEXT NOT NULL,
    origin_uri       TEXT,                     -- file path or system of record
    content_sha256   TEXT,                     -- re-ingest detection
    ingested_at      TEXT NOT NULL,
    period_start     TEXT,                     -- reporting window the artifact covers
    period_end       TEXT,
    is_synthetic     INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic IN (0,1)),
    is_deidentified  INTEGER NOT NULL DEFAULT 0 CHECK (is_deidentified IN (0,1)),
    authority_rank   INTEGER NOT NULL DEFAULT 100  -- lower wins in conflict resolution
);


-- ---------------------------------------------------------------------------
-- 2. PATIENT IDENTITY
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS patients (
    patient_id       TEXT PRIMARY KEY,
    display_name     TEXT,
    date_of_birth    TEXT,
    sex_at_birth     TEXT,
    pronouns         TEXT,
    timezone         TEXT NOT NULL,
    is_synthetic     INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic IN (0,1)),
    created_at       TEXT NOT NULL
);

-- Each source names the patient differently (internal id vs. redacted code).
CREATE TABLE IF NOT EXISTS patient_identifiers (
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id),
    id_type          TEXT NOT NULL             -- internal | patient_code | mrn | redacted
                     CHECK (id_type IN ('internal','patient_code','mrn','redacted')),
    id_value         TEXT,                     -- NULL when redacted in the source
    PRIMARY KEY (patient_id, source_id, id_type)
);

CREATE TABLE IF NOT EXISTS enrollments (
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    program          TEXT NOT NULL,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id),
    enrolled_at      TEXT NOT NULL,
    window_start     TEXT NOT NULL,
    window_end       TEXT NOT NULL,
    practices_start  TEXT,
    PRIMARY KEY (patient_id, program)
);

CREATE TABLE IF NOT EXISTS consents (
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    scope            TEXT NOT NULL,            -- self_report_sharing | healthkit_sharing |
                                               -- journal_ai_summary | voice_note_transcription |
                                               -- hk_type:<HKIdentifier> | passive_mobile_monitoring
    granted          INTEGER NOT NULL CHECK (granted IN (0,1)),
    granted_at       TEXT,
    revoked_at       TEXT,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id),
    PRIMARY KEY (patient_id, scope)
);

CREATE TABLE IF NOT EXISTS devices (
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    device_type      TEXT NOT NULL,            -- iPhone | Apple Watch | ...
    model            TEXT,
    os_version       TEXT,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id),
    PRIMARY KEY (patient_id, device_type)
);


-- ---------------------------------------------------------------------------
-- 3. CLINICAL FACTS
-- Promoted out of the old JSON blobs so conflicting source assertions coexist
-- as rows instead of fighting over one column.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS diagnoses (
    diagnosis_id     TEXT PRIMARY KEY,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    icd10            TEXT NOT NULL,
    description      TEXT NOT NULL,
    rank             TEXT NOT NULL CHECK (rank IN ('primary','secondary')),
    category         TEXT NOT NULL DEFAULT 'psychiatric'
                     CHECK (category IN ('psychiatric','medical')),
    asserted_on      TEXT,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id)
);

CREATE TABLE IF NOT EXISTS medications (
    medication_id    TEXT PRIMARY KEY,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    name             TEXT NOT NULL,
    dose             TEXT,
    route            TEXT,                     -- oral | intranasal | iv
    frequency        TEXT,
    started_on       TEXT,
    ended_on         TEXT,
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','discontinued','held')),
    is_monitored     INTEGER NOT NULL DEFAULT 0 CHECK (is_monitored IN (0,1)),  -- e.g. REMS
    notes            TEXT,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id)
);

CREATE TABLE IF NOT EXISTS care_team (
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    clinician_id     TEXT NOT NULL,
    name             TEXT,
    credential       TEXT,                     -- LPC | MD | APRN, PMHNP
    role             TEXT NOT NULL,            -- primary_therapist | prescriber | ...
    organization     TEXT,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id),
    PRIMARY KEY (patient_id, clinician_id)
);


-- ---------------------------------------------------------------------------
-- 4. ENCOUNTERS AND EVENT TIMELINE
-- `encounters` generalizes the old `sessions` table to every contact type.
-- `clinical_events` is the cross-source timeline that makes integration pay off.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS encounters (
    encounter_id     TEXT PRIMARY KEY,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    encounter_type   TEXT NOT NULL
                     CHECK (encounter_type IN ('intake','therapy_session','psychiatry_followup',
                                               'medication_treatment','hospitalization','check_in')),
    sequence_number  INTEGER,                  -- 1-based within type; NULL if not serialized
    scheduled_start  TEXT NOT NULL,
    duration_min     INTEGER,
    modality         TEXT CHECK (modality IN ('in_person','telehealth','phone')),
    cpt_code         TEXT,
    attended         INTEGER CHECK (attended IN (0,1)),
    clinician_id     TEXT,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id)
);
CREATE INDEX IF NOT EXISTS idx_encounters_patient_time ON encounters (patient_id, scheduled_start);

CREATE TABLE IF NOT EXISTS clinical_events (
    event_id         TEXT PRIMARY KEY,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    category         TEXT NOT NULL
                     CHECK (category IN ('psychosocial_stressor','medical','treatment',
                                         'safety','milestone','administrative')),
    label            TEXT NOT NULL,            -- 'job_loss', 'hospitalization', 'safety_plan_created'
    description      TEXT,
    onset_at         TEXT NOT NULL,
    resolved_at      TEXT,
    valence          INTEGER CHECK (valence IN (-1,0,1)),
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id),
    evidence_ref     TEXT                      -- originating entry_id / section, for drill-down
);
CREATE INDEX IF NOT EXISTS idx_events_patient_time ON clinical_events (patient_id, onset_at);


-- ---------------------------------------------------------------------------
-- 5. ASSESSMENTS
-- One table for every instrument from every source. The CareLinq PHQ-9s carry
-- item detail; the PDF's carry only totals, so `assessment_items` is sparse.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id        TEXT PRIMARY KEY,
    patient_id           TEXT NOT NULL REFERENCES patients(patient_id),
    instrument           TEXT NOT NULL,        -- 'PHQ-9', 'GAD-7', ...
    administered_at      TEXT NOT NULL,
    administration_week  INTEGER,              -- NULL when not part of a weekly series
    total_score          INTEGER NOT NULL,
    max_score            INTEGER NOT NULL,
    severity_band        TEXT CHECK (severity_band IN
                             ('minimal','mild','moderate','moderately_severe','severe')),
    functional_difficulty TEXT CHECK (functional_difficulty IN
                             ('not_difficult_at_all','somewhat_difficult',
                              'very_difficult','extremely_difficult')),
    -- Denormalized safety column. PHQ-9 item 9 drives the highest-priority
    -- alert in the product, so it gets a real indexed column rather than a
    -- JSON reach. NULL means "not captured", which is NOT the same as 0.
    phq9_item9_score     INTEGER CHECK (phq9_item9_score BETWEEN 0 AND 3),
    context_note         TEXT,                 -- 'during hospitalization', 'pretreatment baseline'
    is_baseline          INTEGER NOT NULL DEFAULT 0 CHECK (is_baseline IN (0,1)),
    source_id            TEXT NOT NULL REFERENCES data_sources(source_id)
);
CREATE INDEX IF NOT EXISTS idx_assess_patient_instr ON assessments (patient_id, instrument, administered_at);
CREATE INDEX IF NOT EXISTS idx_assess_item9 ON assessments (patient_id, phq9_item9_score)
    WHERE phq9_item9_score > 0;

CREATE TABLE IF NOT EXISTS assessment_items (
    assessment_id    TEXT NOT NULL REFERENCES assessments(assessment_id),
    item_number      INTEGER NOT NULL,
    item_text        TEXT,
    score            INTEGER NOT NULL,
    PRIMARY KEY (assessment_id, item_number)
);


-- ---------------------------------------------------------------------------
-- 6. SELF-REPORT STREAMS
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mood_checkins (
    checkin_id       TEXT PRIMARY KEY,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    logged_at        TEXT NOT NULL,
    mood             INTEGER CHECK (mood BETWEEN 1 AND 10),      -- 10 best
    anxiety          INTEGER CHECK (anxiety BETWEEN 1 AND 10),   -- 10 worst
    energy           INTEGER CHECK (energy BETWEEN 1 AND 10),    -- 10 best
    note             TEXT,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id)
);
CREATE INDEX IF NOT EXISTS idx_mood_patient_time ON mood_checkins (patient_id, logged_at);

-- emotion_tags was a JSON array; a child table makes tag frequency a GROUP BY.
CREATE TABLE IF NOT EXISTS mood_checkin_tags (
    checkin_id       TEXT NOT NULL REFERENCES mood_checkins(checkin_id),
    tag              TEXT NOT NULL,
    PRIMARY KEY (checkin_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_mood_tags_tag ON mood_checkin_tags (tag);

-- Journals and voice notes share every analysed field, so they share a table
-- and differ by `medium`. Avoids duplicating the NLP columns twice.
CREATE TABLE IF NOT EXISTS narratives (
    narrative_id             TEXT PRIMARY KEY,
    patient_id               TEXT NOT NULL REFERENCES patients(patient_id),
    medium                   TEXT NOT NULL CHECK (medium IN ('journal','voice_note')),
    created_at               TEXT NOT NULL,
    body_text                TEXT,             -- journal text or voice transcript
    word_count               INTEGER,
    duration_sec             INTEGER,          -- voice only
    audio_uri                TEXT,             -- voice only
    transcription_confidence REAL CHECK (transcription_confidence BETWEEN 0 AND 1),
    ai_summary               TEXT,
    sentiment_score          REAL CHECK (sentiment_score BETWEEN -1 AND 1),
    shared_with_clinician    INTEGER NOT NULL DEFAULT 0 CHECK (shared_with_clinician IN (0,1)),
    source_id                TEXT NOT NULL REFERENCES data_sources(source_id)
);
CREATE INDEX IF NOT EXISTS idx_narr_patient_time ON narratives (patient_id, created_at);

-- ai_themes was JSON matched with LIKE '%passive_ideation%'. As a child table
-- the risk-language query becomes an index seek, and `is_risk_flag` lets the
-- alerting rule live in data instead of in a hardcoded string list.
CREATE TABLE IF NOT EXISTS narrative_themes (
    narrative_id     TEXT NOT NULL REFERENCES narratives(narrative_id),
    theme            TEXT NOT NULL,
    PRIMARY KEY (narrative_id, theme)
);
CREATE INDEX IF NOT EXISTS idx_narr_themes_theme ON narrative_themes (theme);

CREATE TABLE IF NOT EXISTS theme_definitions (
    theme            TEXT PRIMARY KEY,
    display_name     TEXT,
    is_risk_flag     INTEGER NOT NULL DEFAULT 0 CHECK (is_risk_flag IN (0,1)),
    alert_priority   INTEGER                   -- 1 = highest
);


-- ---------------------------------------------------------------------------
-- 7. PRACTICES
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS practices (
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    practice_id      TEXT NOT NULL,            -- unique per patient, not globally
    name             TEXT NOT NULL,
    track            TEXT NOT NULL CHECK (track IN ('make_it_happen','meet_the_moment')),
    target_per_week  INTEGER,                  -- NULL for meet_the_moment
    trigger_text     TEXT,                     -- source field is `trigger` (SQL keyword)
    created_at       TEXT NOT NULL,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id),
    PRIMARY KEY (patient_id, practice_id),
    CHECK ((track = 'make_it_happen') = (target_per_week IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS practice_daily_logs (
    log_id           TEXT PRIMARY KEY,
    patient_id       TEXT NOT NULL,
    practice_id      TEXT NOT NULL,
    log_date         TEXT NOT NULL,            -- `date` is reserved in some dialects
    completed        INTEGER NOT NULL CHECK (completed IN (0,1)),
    FOREIGN KEY (patient_id, practice_id) REFERENCES practices(patient_id, practice_id)
);
CREATE INDEX IF NOT EXISTS idx_pdl_patient_date ON practice_daily_logs (patient_id, log_date);

CREATE TABLE IF NOT EXISTS practice_weekly_cycles (
    patient_id       TEXT NOT NULL,
    practice_id      TEXT NOT NULL,
    week             INTEGER NOT NULL,         -- aligns with assessments.administration_week
    cycle_start      TEXT NOT NULL,            -- Monday
    cycle_end        TEXT NOT NULL,            -- Sunday
    target           INTEGER NOT NULL,
    completed        INTEGER NOT NULL,
    met_target       INTEGER NOT NULL CHECK (met_target IN (0,1)),
    PRIMARY KEY (patient_id, practice_id, week),
    FOREIGN KEY (patient_id, practice_id) REFERENCES practices(patient_id, practice_id)
);

CREATE TABLE IF NOT EXISTS meet_the_moment_logs (
    log_id           TEXT PRIMARY KEY,
    patient_id       TEXT NOT NULL,
    practice_id      TEXT NOT NULL,
    logged_at        TEXT NOT NULL,
    situation        TEXT,
    emotion_named    TEXT,
    intensity_before INTEGER CHECK (intensity_before BETWEEN 0 AND 10),
    intensity_after  INTEGER CHECK (intensity_after BETWEEN 0 AND 10),
    FOREIGN KEY (patient_id, practice_id) REFERENCES practices(patient_id, practice_id)
);


-- ---------------------------------------------------------------------------
-- 8. PASSIVE MONITORING
-- Two daily streams now (HealthKit physiology, Behavidence MHSS) and more
-- later. A long table absorbs new metrics as rows; the wide views below
-- restore the ergonomics the dashboard wants.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS metric_definitions (
    metric_code      TEXT PRIMARY KEY,         -- HealthKit identifier verbatim, or BHVD_*
    display_name     TEXT NOT NULL,
    unit             TEXT NOT NULL,
    domain           TEXT NOT NULL
                     CHECK (domain IN ('physiology','activity','sleep','behavioral_similarity')),
    aggregation      TEXT,                     -- daily_mean_of_samples | sleep_mean | sum
    requires_device  TEXT,                     -- 'Apple Watch' | 'phone' | NULL
    higher_is_better INTEGER CHECK (higher_is_better IN (0,1)),
    is_diagnostic    INTEGER NOT NULL DEFAULT 0 CHECK (is_diagnostic IN (0,1))
);

CREATE TABLE IF NOT EXISTS daily_observations (
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    obs_date         TEXT NOT NULL,
    metric_code      TEXT NOT NULL REFERENCES metric_definitions(metric_code),
    value            REAL,                     -- NULL = captured window, no reading
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id),
    PRIMARY KEY (patient_id, obs_date, metric_code)
);
CREATE INDEX IF NOT EXISTS idx_obs_metric_date ON daily_observations (patient_id, metric_code, obs_date);

-- Why a value is missing, held once per day instead of once per metric.
CREATE TABLE IF NOT EXISTS observation_coverage (
    patient_id          TEXT NOT NULL REFERENCES patients(patient_id),
    obs_date            TEXT NOT NULL,
    watch_worn          INTEGER CHECK (watch_worn IN (0,1)),
    phone_monitoring    INTEGER CHECK (phone_monitoring IN (0,1)),
    sleep_session_present INTEGER CHECK (sleep_session_present IN (0,1)),
    PRIMARY KEY (patient_id, obs_date)
);

CREATE TABLE IF NOT EXISTS sleep_sessions (
    patient_id              TEXT NOT NULL REFERENCES patients(patient_id),
    night_of                TEXT NOT NULL,     -- evening the night started
    device_source           TEXT,
    in_bed_start            TEXT NOT NULL,
    in_bed_end              TEXT NOT NULL,
    sleep_onset_latency_min INTEGER,
    total_asleep_min        INTEGER,
    awake_min               INTEGER,
    awakenings              INTEGER,
    asleep_core_min         INTEGER,
    asleep_deep_min         INTEGER,
    asleep_rem_min          INTEGER,
    sleep_efficiency        REAL CHECK (sleep_efficiency BETWEEN 0 AND 1),
    source_id               TEXT NOT NULL REFERENCES data_sources(source_id),
    PRIMARY KEY (patient_id, night_of)
);


-- ---------------------------------------------------------------------------
-- 9. SAFETY
-- Separated from assessments because risk is asserted at encounters and in
-- narrative text, not only by an instrument score.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS risk_assessments (
    risk_id          TEXT PRIMARY KEY,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    assessed_at      TEXT NOT NULL,
    encounter_id     TEXT REFERENCES encounters(encounter_id),
    ideation         TEXT CHECK (ideation IN ('none','passive','active')),
    has_plan         INTEGER CHECK (has_plan IN (0,1)),
    has_intent       INTEGER CHECK (has_intent IN (0,1)),
    chronic_risk     TEXT CHECK (chronic_risk IN ('low','moderate','elevated','high')),
    finding          TEXT,
    significance     TEXT,
    detected_by      TEXT NOT NULL
                     CHECK (detected_by IN ('instrument','clinician','nlp_narrative')),
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id)
);
CREATE INDEX IF NOT EXISTS idx_risk_patient_time ON risk_assessments (patient_id, assessed_at);

CREATE TABLE IF NOT EXISTS protective_factors (
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    factor           TEXT NOT NULL,            -- 'grandmother_support', 'future_orientation'
    noted_at         TEXT,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id),
    PRIMARY KEY (patient_id, factor)
);

CREATE TABLE IF NOT EXISTS safety_plans (
    plan_id          TEXT PRIMARY KEY,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    created_at       TEXT NOT NULL,
    created_with     TEXT,                     -- clinician_id
    escalation_note  TEXT,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id)
);


-- ---------------------------------------------------------------------------
-- 10. RTM / BILLING
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS rtm_periods (
    rtm_period_id         TEXT PRIMARY KEY,
    patient_id            TEXT NOT NULL REFERENCES patients(patient_id),
    period_start          TEXT NOT NULL,
    period_end            TEXT NOT NULL,
    monitoring_days       INTEGER NOT NULL,
    threshold_days        INTEGER NOT NULL DEFAULT 16,
    threshold_met         INTEGER NOT NULL CHECK (threshold_met IN (0,1)),
    review_minutes        INTEGER NOT NULL DEFAULT 0,
    assessments_sent      INTEGER NOT NULL DEFAULT 0,
    candidate_cpt         TEXT,                -- '98980'
    -- The source PDF marks 98980 "eligible" while recording 0 review minutes.
    -- Eligibility is an assertion to be reviewed, never an inference.
    eligibility_asserted  INTEGER CHECK (eligibility_asserted IN (0,1)),
    eligibility_note      TEXT,
    source_id             TEXT NOT NULL REFERENCES data_sources(source_id)
);

CREATE TABLE IF NOT EXISTS rtm_activities (
    activity_id      TEXT PRIMARY KEY,
    rtm_period_id    TEXT NOT NULL REFERENCES rtm_periods(rtm_period_id),
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    occurred_at      TEXT,
    activity_type    TEXT NOT NULL
                     CHECK (activity_type IN ('interactive_communication','data_review',
                                              'treatment_management','assessment_sent')),
    minutes          INTEGER,
    description      TEXT,
    clinician_id     TEXT
);

CREATE TABLE IF NOT EXISTS care_plan_items (
    plan_item_id     TEXT PRIMARY KEY,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    priority_area    TEXT NOT NULL,            -- 'Spravato', 'Safety', 'Medical coordination'
    plan_text        TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','completed','cancelled')),
    recorded_at      TEXT,
    source_id        TEXT NOT NULL REFERENCES data_sources(source_id)
);


-- ---------------------------------------------------------------------------
-- 11. DATA QUALITY
-- The sources contradict each other. Conflicts are data, not a README note:
-- the dashboard can surface "2 unresolved conflicts" instead of silently
-- picking a winner.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS source_conflicts (
    conflict_id      TEXT PRIMARY KEY,
    patient_id       TEXT NOT NULL REFERENCES patients(patient_id),
    field_path       TEXT NOT NULL,            -- 'clinical.primary_diagnosis.icd10'
    severity         TEXT NOT NULL CHECK (severity IN ('info','warning','blocking')),
    value_a          TEXT,
    source_a         TEXT NOT NULL REFERENCES data_sources(source_id),
    value_b          TEXT,
    source_b         TEXT NOT NULL REFERENCES data_sources(source_id),
    resolution       TEXT NOT NULL DEFAULT 'unresolved'
                     CHECK (resolution IN ('unresolved','prefer_a','prefer_b',
                                           'both_valid','manual_override')),
    resolved_value   TEXT,
    resolved_by      TEXT,
    resolved_at      TEXT,
    note             TEXT
);
CREATE INDEX IF NOT EXISTS idx_conflicts_open ON source_conflicts (patient_id, resolution)
    WHERE resolution = 'unresolved';


-- ---------------------------------------------------------------------------
-- 12. VIEWS — restore the wide shape over the long observation table
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS v_safety_signals;
DROP VIEW IF EXISTS v_daily_integrated;
DROP VIEW IF EXISTS v_mhss_daily;
DROP VIEW IF EXISTS v_healthkit_daily;

CREATE VIEW v_healthkit_daily AS
SELECT
    o.patient_id,
    o.obs_date,
    c.watch_worn,
    MAX(CASE WHEN o.metric_code = 'HKQuantityTypeIdentifierStepCount'                THEN o.value END) AS step_count,
    MAX(CASE WHEN o.metric_code = 'HKQuantityTypeIdentifierActiveEnergyBurned'       THEN o.value END) AS active_energy_kcal,
    MAX(CASE WHEN o.metric_code = 'HKQuantityTypeIdentifierAppleExerciseTime'        THEN o.value END) AS exercise_min,
    MAX(CASE WHEN o.metric_code = 'HKQuantityTypeIdentifierRestingHeartRate'         THEN o.value END) AS resting_hr,
    MAX(CASE WHEN o.metric_code = 'HKQuantityTypeIdentifierHeartRateVariabilitySDNN' THEN o.value END) AS hrv_sdnn_ms,
    MAX(CASE WHEN o.metric_code = 'HKQuantityTypeIdentifierRespiratoryRate'          THEN o.value END) AS respiratory_rate,
    MAX(CASE WHEN o.metric_code = 'HKQuantityTypeIdentifierTimeInDaylight'           THEN o.value END) AS time_in_daylight_min,
    MAX(CASE WHEN o.metric_code = 'HKCategoryTypeIdentifierMindfulSession'           THEN o.value END) AS mindful_min
FROM daily_observations o
LEFT JOIN observation_coverage c
       ON c.patient_id = o.patient_id AND c.obs_date = o.obs_date
GROUP BY o.patient_id, o.obs_date, c.watch_worn;

CREATE VIEW v_mhss_daily AS
SELECT
    patient_id,
    obs_date,
    MAX(CASE WHEN metric_code = 'BHVD_MHSS_ANXIETY'    THEN value END) AS mhss_anxiety,
    MAX(CASE WHEN metric_code = 'BHVD_MHSS_STRESS'     THEN value END) AS mhss_stress,
    MAX(CASE WHEN metric_code = 'BHVD_MHSS_DEPRESSION' THEN value END) AS mhss_depression,
    MAX(CASE WHEN metric_code = 'BHVD_MHSS_ADHD'       THEN value END) AS mhss_adhd
FROM daily_observations
WHERE metric_code LIKE 'BHVD_MHSS_%'
GROUP BY patient_id, obs_date;

-- The body-mind overlay: every daily stream on one row.
CREATE VIEW v_daily_integrated AS
SELECT
    h.patient_id,
    h.obs_date,
    h.watch_worn,
    h.step_count, h.resting_hr, h.hrv_sdnn_ms, h.time_in_daylight_min,
    s.total_asleep_min, s.sleep_efficiency, s.in_bed_start,
    m.mood, m.anxiety, m.energy,
    x.mhss_anxiety, x.mhss_depression, x.mhss_stress, x.mhss_adhd
FROM v_healthkit_daily h
LEFT JOIN sleep_sessions s ON s.patient_id = h.patient_id AND s.night_of = h.obs_date
LEFT JOIN v_mhss_daily   x ON x.patient_id = h.patient_id AND x.obs_date = h.obs_date
LEFT JOIN (
    SELECT patient_id, substr(logged_at, 1, 10) AS d,
           AVG(mood) AS mood, AVG(anxiety) AS anxiety, AVG(energy) AS energy
      FROM mood_checkins GROUP BY patient_id, substr(logged_at, 1, 10)
) m ON m.patient_id = h.patient_id AND m.d = h.obs_date;

-- Unified safety feed: instrument, clinician and NLP signals in one timeline.
CREATE VIEW v_safety_signals AS
SELECT patient_id, administered_at AS signal_at, 'phq9_item9' AS signal,
       CAST(phq9_item9_score AS TEXT) AS detail, 1 AS priority, source_id
  FROM assessments WHERE phq9_item9_score > 0
UNION ALL
SELECT r.patient_id, r.assessed_at, 'risk_assessment',
       COALESCE(r.ideation, '') || CASE WHEN r.has_plan = 1 THEN ' +plan' ELSE '' END,
       1, r.source_id
  FROM risk_assessments r WHERE r.ideation IN ('passive','active')
UNION ALL
SELECT n.patient_id, n.created_at, 'risk_language', t.theme,
       COALESCE(d.alert_priority, 2), n.source_id
  FROM narratives n
  JOIN narrative_themes t  ON t.narrative_id = n.narrative_id
  JOIN theme_definitions d ON d.theme = t.theme AND d.is_risk_flag = 1;


-- ---------------------------------------------------------------------------
-- 13. REFERENCE DATA (not patient data — safe to ship with the DDL)
-- ---------------------------------------------------------------------------

INSERT INTO metric_definitions
    (metric_code, display_name, unit, domain, aggregation, requires_device, higher_is_better, is_diagnostic)
VALUES
    ('HKQuantityTypeIdentifierStepCount',                'Steps',              'count',     'activity',  'sum',                  NULL,          1, 0),
    ('HKQuantityTypeIdentifierActiveEnergyBurned',       'Active energy',      'kcal',      'activity',  'sum',                  NULL,          1, 0),
    ('HKQuantityTypeIdentifierAppleExerciseTime',        'Exercise time',      'min',       'activity',  'sum',                  'Apple Watch', 1, 0),
    ('HKQuantityTypeIdentifierRestingHeartRate',         'Resting HR',         'count/min', 'physiology','daily_mean_of_samples','Apple Watch', 0, 0),
    ('HKQuantityTypeIdentifierHeartRateVariabilitySDNN', 'HRV (SDNN)',         'ms',        'physiology','daily_mean_of_samples','Apple Watch', 1, 0),
    ('HKQuantityTypeIdentifierRespiratoryRate',          'Respiratory rate',   'count/min', 'physiology','sleep_mean',           'Apple Watch', 0, 0),
    ('HKQuantityTypeIdentifierTimeInDaylight',           'Time in daylight',   'min',       'activity',  'sum',                  'Apple Watch', 1, 0),
    ('HKCategoryTypeIdentifierMindfulSession',           'Mindful minutes',    'min',       'activity',  'sum',                  NULL,          1, 0),
    ('BHVD_MHSS_ANXIETY',    'MHSS anxiety similarity',    'percent', 'behavioral_similarity', NULL, 'phone', 0, 0),
    ('BHVD_MHSS_STRESS',     'MHSS stress similarity',     'percent', 'behavioral_similarity', NULL, 'phone', 0, 0),
    ('BHVD_MHSS_DEPRESSION', 'MHSS depression similarity', 'percent', 'behavioral_similarity', NULL, 'phone', 0, 0),
    ('BHVD_MHSS_ADHD',       'MHSS ADHD similarity',       'percent', 'behavioral_similarity', NULL, 'phone', 0, 0)
ON CONFLICT DO NOTHING;

INSERT INTO theme_definitions (theme, display_name, is_risk_flag, alert_priority) VALUES
    ('passive_ideation', 'Passive suicidal ideation', 1, 1),
    ('hopelessness',     'Hopelessness',              1, 2),
    ('catastrophizing',  'Catastrophic thinking',     1, 3),
    ('safety_planning',  'Safety planning',           0, NULL),
    ('job_loss',         'Job loss',                  0, NULL),
    ('financial_stress', 'Financial stress',          0, NULL),
    ('practice_lapse',   'Practice lapse',            0, NULL)
ON CONFLICT DO NOTHING;
