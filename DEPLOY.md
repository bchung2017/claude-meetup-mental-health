# Deploying to Render + Supabase

## 1. Supabase: get a Session-pooler connection string

1. Supabase dashboard → your project → **Connect** (top bar) → **Connection string** tab.
2. Pick **Session pooler** (not Transaction pooler, not Direct). Mode matters: the app pins
   `search_path` per connection, which the transaction pooler resets between statements.
   The URI looks like:
   ```
   postgresql://postgres.<project-ref>:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```
3. Replace `[YOUR-PASSWORD]` with the database password. If it contains `@`, `:`, `/`, `#`, `?`
   or `%`, URL-encode it (`@` → `%40`, etc.). Do not append `?sslmode=...` or any other query
   string; the app adds its own.
4. No schema or table setup is needed. On first request the app runs
   `CREATE SCHEMA IF NOT EXISTS mental_health` and creates `mental_health.entries`.
   Nothing in `public` is read or written.

## 2. Render: create the service from the Blueprint

1. Render dashboard → **New** → **Blueprint**.
2. Connect the GitHub repo `bchung2017/claude-meetup-mental-health`, branch `main`.
   Render reads `render.yaml`:
   - runtime Python 3.12, `pip install -r requirements.txt`, `gunicorn wsgi:app`
   - health check on `/api/health`
   - `DB_SCHEMA=mental_health` preset
   - `DATABASE_URL` marked `sync: false`, so Render prompts for it
3. When prompted, paste the Session-pooler URI from step 1 as `DATABASE_URL`. Click **Apply**.
4. First deploy takes 1–2 minutes. The service URL is `https://mental-health-charts.onrender.com`
   (or whatever Render assigns if the name is taken).

To add or change env vars later: service → **Environment** → edit → **Save, rebuild, and deploy**.

## 3. Verify

```bash
curl https://<service>.onrender.com/api/health
# {"backend":"postgres","ok":true}
```

`"backend":"sqlite"` means `DATABASE_URL` is not set on the service. Data would then live on
Render's ephemeral disk and vanish on every deploy or restart.

Optionally seed the sample rows from a Render shell (service → **Shell**) or locally with the
same `DATABASE_URL`:

```bash
DATABASE_URL='postgresql://...' DB_SCHEMA=mental_health python scripts/seed_sample.py
```

## 4. Redeploys

Every push to `main` auto-deploys. The schema DDL is idempotent, so redeploys are safe; there is
no migration step.

## Gotchas

- **Free tier spin-down.** Render free web services sleep after 15 min idle; the first request
  afterward takes ~30–60 s. Upgrade the plan in `render.yaml` (`plan: starter`) if that matters.
- **Supabase free tier pauses** inactive projects after 7 days. The app will fail at startup with
  a connection error until the project is restored from the Supabase dashboard.
- **IPv4.** Render egress is IPv4-only. The pooler host (`*.pooler.supabase.com`) is IPv4-friendly;
  the direct `db.<ref>.supabase.co` host is IPv6-first and will not connect without the IPv4 add-on.
- **Pool size.** `PGPOOL_MAX` defaults to 3 per gunicorn worker. The Session pooler on the free
  tier allows 15 client connections per pooler instance; keep workers × `PGPOOL_MAX` under that.
- **Sharing the Supabase project.** Other apps can use the same project with a different
  `DB_SCHEMA`; each app's tables live in its own schema and never collide.
