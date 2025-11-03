CREATE TABLE IF NOT EXISTS articles(
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  domain TEXT NOT NULL,
  title TEXT,
  lang TEXT CHECK (lang IN ('en','es')) NOT NULL,
  pub_time TIMESTAMPTZ,
  snippet TEXT,
  text_hash TEXT NOT NULL,
  create_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analyses(
  article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  summary TEXT,
  sentiment TEXT CHECK (sentiment IN ('positive','neutral','negative')),
  confidence DOUBLE PRECISION,
  cost_cents INTEGER DEFAULT 0,
  model_version TEXT,
  create_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY(article_id, model_version)
);

CREATE TABLE IF NOT EXISTS ingest_log(
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  status TEXT NOT NULL,
  note TEXT,
  create_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_articles_text_hash ON articles(text_hash);
CREATE INDEX IF NOT EXISTS idx_articles_create_time ON articles(create_time);
CREATE INDEX IF NOT EXISTS idx_analyses_article_id ON analyses(article_id);
