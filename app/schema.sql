CREATE TABLE IF NOT EXISTS entries (
  id         TEXT PRIMARY KEY,
  created_at BIGINT  NOT NULL,
  depression INTEGER NOT NULL,
  adhd       INTEGER NOT NULL,
  note       TEXT    NOT NULL
);
