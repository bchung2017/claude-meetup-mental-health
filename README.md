# Symptom Tracker

Small Flask site for one person: log daily depression and ADHD scores (0–100, matching the
Behavidence MHSS similarity scale) and a medication adherence score (0–100), and see them as
three lines over time.
Runs on SQLite with zero config; set `DATABASE_URL` to persist in Postgres/Supabase,
isolated in its own schema so it can share a Supabase project with other apps.

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
flask --app wsgi run --debug    # http://127.0.0.1:5000, SQLite at ./mental_health.db
```

## Tether (chat tab)

Second tab: a chatbot called Tether, backed by Claude Opus 5.5 through the Anthropic API.
It needs an API key from <https://console.anthropic.com/settings/keys>.

**Locally:** copy `.env.example` to `.env` and set the key (the app loads `.env` on startup):

```bash
cp .env.example .env
# edit .env: ANTHROPIC_API_KEY=sk-ant-...
flask --app wsgi run --debug
```

Or export it in the shell instead: `ANTHROPIC_API_KEY=sk-ant-... flask --app wsgi run --debug`.
`.env` is gitignored; never commit the key.

**On Render:** service → **Environment** → add `ANTHROPIC_API_KEY` → **Save, rebuild, and
deploy**. `render.yaml` already declares it with `sync: false`, so a fresh Blueprint deploy
prompts for it.

Without the key the tab loads but shows "ANTHROPIC_API_KEY not set" and the input is disabled.

How it works:

- `app/tether/prompt.py` is the prompt harness. The system prompt is built from named
  sections (identity, stance, safety) so each can be edited independently. It is frozen for
  the life of a conversation and prompt-cached. The tracker snapshot (last 14 entries from
  the last 30 days, all three scores) is injected once, as a mid-conversation `system` message after the first
  user turn, so the cached prefix and the model's thinking blocks stay valid.
- `app/tether/routes.py` streams each reply over server-sent events. The server is
  stateless; the browser keeps the conversation in `sessionStorage` and replays it on every
  turn, assistant content blocks included.
- Adaptive thinking is on (it cannot be turned off on Opus 5.5); `TETHER_EFFORT` controls
  depth (`low`…`max`, default `medium`). Server-side refusal fallback is enabled
  (`fallbacks: "default"`), so a classifier false positive is retried on another model
  rather than surfacing as a dead turn.
- Env: `ANTHROPIC_API_KEY` (required), `TETHER_MODEL` (default `claude-opus-5-5`),
  `TETHER_EFFORT` (default `medium`).

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
| POST | `/api/entries` | `{"depression": 0-100, "adhd": 0-100, "adherence": 0-100, "note": ""}` |
| DELETE | `/api/entries/<id>` | – |
| GET | `/api/tether/health` | – → `{"configured": bool, "model": "..."}` |
| POST | `/api/tether/chat` | `{"messages": [...]}` full history ending with a user turn; responds with SSE events `context`, `text`, `done`, `error` |

## Per-patient model

Beyond the single-person `entries` table, the schema carries the CareLinq per-patient streams.
Full model with ER diagram: [docs/per-patient-schema.md](docs/per-patient-schema.md); source data
and clinical story: `data/sample/README.md`. All tables are keyed by
`patient_id`:

| Table | Source |
|---|---|
| `patients`, `sessions` | `patient.json` |
| `phq9_responses` (with `item9_score` denormalized), `mood_checkins`, `journal_entries`, `voice_notes` | `self_report.json` |
| `practices`, `practice_daily_logs`, `practice_weekly_cycles`, `meet_the_moment_logs` | `self_report.json` → `practices` |
| `sleep_sessions`, `daily_metrics` (HealthKit identifiers flattened to columns) | `healthkit.json` |

Read endpoints:

| Method | Path |
|---|---|
| GET | `/api/patients` |
| GET | `/api/patients/<patient_id>` |
| GET | `/api/patients/<patient_id>/<stream>` where stream is any table above except `patients` |

Import a bundle directory (defaults to `data/sample`; re-runs skip existing keys):

```bash
python scripts/import_carelinq.py [dir]
```

With `SEED_SAMPLE_DATA=1` the app imports `data/sample` on startup when `patients` is empty.

## Sample data

```bash
python scripts/seed_sample.py
```

Loads the 19 daily depression/ADHD rows from the sample Behavidence report, with synthetic
adherence scores, onto consecutive days ending today. Refuses to run if the table already has rows.

Existing databases get the `adherence` column added on startup (defaults to 0).

## Migrate SQLite → Postgres

```bash
DATABASE_URL=... DB_SCHEMA=mental_health python scripts/migrate_sqlite_to_pg.py mental_health.db
```

Refuses to run if the target table already has rows.
