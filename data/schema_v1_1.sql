PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS articles(
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    domain TEXT NOT NULL,
    title TEXT,
    lang TEXT CHECK (lang IN ('en','es')) NOT NULL,
    pub_time TEXT,   -- ISO 8601
    snippet TEXT,
    text_hash TEXT NOT NULL,
    create_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses(
    article_id TEXT NOT NULL,
    summary TEXT,
    sentiment TEXT CHECK (sentiment IN ('positive','neutral','negative')),
    confidence REAL,
    cost_cents INTEGER DEFAULT 0,
    model_version TEXT,
    create_time TEXT NOT NULL,
    PRIMARY KEY(article_id, model_version),
    FOREIGN KEY(article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS ingest_log(
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  status TEXT NOT NULL,
  note TEXT,
  create_time TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_articles_text_hash ON articles(text_hash);
CREATE INDEX IF NOT EXISTS idx_articles_create_time ON articles(create_time);
CREATE INDEX IF NOT EXISTS idx_analyses_article_id ON analyses(article_id);