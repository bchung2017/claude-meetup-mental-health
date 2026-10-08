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

## Sample data

```bash
python scripts/seed_sample.py
```

Loads the 19 daily depression/ADHD rows from the sample Behavidence report, with synthetic
meds-taken flags, onto consecutive days ending today. Refuses to run if the table already has rows.

Existing databases get the `meds_taken` column added on startup (defaults to not taken).

## Migrate SQLite → Postgres

```bash
DATABASE_URL=... DB_SCHEMA=mental_health python scripts/migrate_sqlite_to_pg.py mental_health.db
```

Refuses to run if the target table already has rows.
