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

Tether is a clinician's assistant backed by Claude Opus 5.5 through the Anthropic API. It is
the second tab on the patient dashboard (`/`), following the patient selector, and also on
`/tracker`. It prepares for the session with the selected patient, flags concerns (PHQ-9 item 9, risk
language, deterioration, engagement and sleep drops) and answers follow-up questions from the
record. It needs an API key from <https://console.anthropic.com/settings/keys>.

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

### Voice (optional)

Set `ELEVENLABS_API_KEY` (same places as the Anthropic key) and each Tether reply gets a
**Speak** button that plays it through ElevenLabs text-to-speech via `POST /api/tether/speak`.
`ELEVENLABS_VOICE_ID` (default `JBFqnCBsd6RMkjVDRZzb`) and `ELEVENLABS_MODEL_ID` (default
`eleven_multilingual_v2`) pick the voice and model. Without the key the button is hidden.

### The meta prompt

The meta prompt is a plain text/Markdown file, read once at startup:
`app/tether/prompts/clinician.md`. Edit it and restart (or redeploy) to change Tether's
instructions. To use a different file without touching the repo, point `TETHER_PROMPT_FILE`
at it (on Render, add it as an env var alongside a Secret File, or mount the file in the
repo and set the path).

Two rules for what goes where:

- **Static instructions** (role, protocol, format) go in the prompt file. It becomes the
  top-level `system`, frozen for the life of a conversation and prompt-cached, so length is
  cheap after the first request. An existing chat keeps its prompt until "New chat".
- **Data** goes through `patient_record()` in `app/tether/prompt.py`, delivered as a
  mid-conversation `system` message after the clinician's first turn. Changing the top-level
  `system` mid-conversation would break the cache and, on newer accounts, invalidate the
  model's thinking blocks.

### How it works

- `app/tether/prompt.py` loads the prompt file and renders the patient record: profile,
  sessions, PHQ-9 responses, mood check-ins, journal entries, voice note transcripts,
  practices with weekly rollups, meet-the-moment logs, sleep sessions, daily metrics, plus
  the Behavidence and adherence scores from the tracker. The whole record (roughly 20K
  tokens for the sample patient) is sent once per conversation and cache-read after that.
- `app/tether/routes.py` streams each reply over server-sent events. The server is
  stateless; the browser keeps the conversation in `sessionStorage` and replays it on every
  turn, assistant content blocks included.
- Adaptive thinking is on (it cannot be turned off on Opus 5.5); `TETHER_EFFORT` controls
  depth (`low`…`max`, default `medium`). Server-side refusal fallback is enabled
  (`fallbacks: "default"`), so a classifier false positive is retried on another model
  rather than surfacing as a dead turn.
- Env: `ANTHROPIC_API_KEY` (required), `TETHER_MODEL` (default `claude-opus-5-5`),
  `TETHER_EFFORT` (default `medium`), `TETHER_PROMPT_FILE` (default
  `app/tether/prompts/clinician.md`), `TETHER_PATIENT_ID` (fallback when the page sends no patient; default: first patient on file).

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
| GET | `/api/tether/health?patient_id=` | – → `{"configured": bool, "model": "...", "patient": "...", "tts": bool}` |
| POST | `/api/tether/speak` | `{"text": "..."}` → `audio/mpeg` stream (needs `ELEVENLABS_API_KEY`) |
| POST | `/api/tether/chat` | `{"messages": [...], "patient_id": "..."}` full history ending with a user turn; responds with SSE events `context`, `text`, `done`, `error` |

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

The single-person tracker (`/tracker`) is seeded separately by `scripts/seed_sample.py`: 19 daily
depression/ADHD rows with synthetic adherence scores. `--replace` deletes existing entries first.

Without shell access (Render free tier), set `SEED_SAMPLE_DATA=replace` on the service instead:
every boot then wipes `entries` and reseeds. Set it back to `1` once the chart looks right, or
every restart will keep wiping your real entries.

## Migrate SQLite → Postgres

```bash
DATABASE_URL=... DB_SCHEMA=mental_health python scripts/migrate_sqlite_to_pg.py mental_health.db
```

Refuses to run if the target table already has rows.
