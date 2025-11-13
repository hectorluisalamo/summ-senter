CREATE TABLE IF NOT EXISTS api_cache(
  cache_key TEXT PRIMARY KEY,
  payload   TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_api_cache_exp ON api_cache(expires_at);