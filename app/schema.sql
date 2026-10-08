CREATE TABLE IF NOT EXISTS entries (
  id         TEXT PRIMARY KEY,
  created_at BIGINT  NOT NULL,
  depression INTEGER NOT NULL,
  adhd       INTEGER NOT NULL,
  meds_taken INTEGER NOT NULL DEFAULT 0,
  note       TEXT    NOT NULL
);
