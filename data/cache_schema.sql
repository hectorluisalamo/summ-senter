CREATE UNLOGGED TABLE IF NOT EXISTS http_cache (
  cache_key  TEXT PRIMARY KEY,
  payload    JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_http_cache_key_cover
  ON http_cache (cache_key) INCLUDE (expires_at, payload);
CREATE INDEX IF NOT EXISTS idx_http_cache_expires ON http_cache (expires_at);
