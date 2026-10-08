# Symptom Tracker

Small Flask site for one person: log daily depression and ADHD scores (0–100, matching the
Behavidence MHSS similarity scale) plus whether meds were taken, and see the scores as two
lines over time with a green/red medication strip under them.
Runs on SQLite with zero config; set `DATABASE_URL` to persist in Postgres/Supabase,
isolated in its own schema so it can share a Supabase project with other apps.

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
flask --app wsgi run --debug    # http://127.0.0.1:5000, SQLite at ./mental_health.db
```

## Deploy on Render

Step-by-step in [DEPLOY.md](DEPLOY.md). Summary:

`render.yaml` defines the web service (gunicorn). Create a Blueprint from this repo,
then set `DATABASE_URL` in the service's environment:

- Supabase → Project Settings → Database → Connection string → **Session pooler** (port 5432).
  The transaction pooler (6543) will not preserve `search_path` and must not be used.
- `DB_SCHEMA` defaults to `mental_health` in `render.yaml`; all tables land in that
  schema, nothing in `public` is touched.

Leave `DATABASE_URL` unset and the service falls back to SQLite on Render's ephemeral disk
(data is lost on redeploy).

## API

| Method | Path | Body / query |
|---|---|---|
| GET | `/api/health` | – |
| GET | `/api/entries?days=30` | `days=0` for all |
| POST | `/api/entries` | `{"depression": 0-100, "adhd": 0-100, "meds_taken": true/false, "note": ""}` |
| DELETE | `/api/entries/<id>` | – |

## Per-patient model

Schema: `app/schema.sql` is the integrated DDL from `docs/integrated-patient-schema.md` (33 tables,
4 views), made idempotent so it applies on every startup. Tables keyed by `patient_id`; every
clinical fact carries a `source_id`.

Dashboard at `/`: patient dropdown, PHQ-9 / GAD-7 weekly totals with severity bands and clinical
event markers, daily mood/anxiety/energy, Behavidence MHSS similarity, sleep / HRV / steps,
safety-signal feed (`v_safety_signals`), recent narratives, and weekly practice targets.

| Method | Path |
|---|---|
| GET | `/api/patients` — roster with diagnoses, latest PHQ-9, safety-signal count |
| GET | `/api/patients/<id>/dashboard` — everything the dashboard renders, one call |
| GET | `/api/patients/<id>/<relation>` — any patient-scoped table or view |

## Sample data

Four synthetic patients under `data/patients/<patient_id>/` in CareLinq bundle format
(`patient.json`, `self_report.json`, `healthkit.json`, `behavidence.json`):

| Patient | Profile |
|---|---|
| Maya R. `pt_7f3a9c21` | MDD recurrent moderate + insomnia; layoff dip with passive ideation and safety plan (hand-authored, `data/patients/pt_7f3a9c21/README.md`) |
| Daniel K. `pt_b2c4e8d1` | GAD + ADHD; PHQ-9 and GAD-7; work-crunch relapse, exposure milestone |
| Elena M. `pt_c9d1a3f7` | No diagnosis; wellness monitoring; half-marathon arc |
| Marcus T. `pt_d4e6b2a9` | No diagnosis; wellness monitoring; one-week illness dip |

Regenerate the three generated patients (and Maya's MHSS stream) with `python data/generate_cohort.py`.
Import with `python scripts/import_patients.py [dir]`; with `SEED_SAMPLE_DATA=1` the app imports
all bundles on startup when `patients` is empty. A database carrying the previous 12-table
per-patient layout is reset automatically on first boot.

## Migrate SQLite → Postgres

```bash
DATABASE_URL=... DB_SCHEMA=mental_health python scripts/migrate_sqlite_to_pg.py mental_health.db
```

Refuses to run if the target table already has rows.
