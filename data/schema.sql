-- articles
CREATE TABLE IF NOT EXISTS articles(
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    domain TEXT NOT NULL,
    title TEXT,
    lang TEXT CHECK (lang IN ('en','es')),
    pub_time TIMESTAMP,
    snippet TEXT,                   -- ≤ 3000 chars
    text_hash TEXT NOT NULL,             -- SHA1 normalized_text
    fetch_status TEXT,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- analyses
CREATE TABLE IF NOT EXISTS analyses(
    article_id TEXT NOT NULL,
    summary TEXT,
    key_sentences JSON,
    sentiment TEXT CHECK (sentiment IN ('positive','neutral','negative')),
    confidence REAL,
    cost_cents INTEGER,
    tokens INTEGER,
    model_version TEXT,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(article_id) REFERENCES articles(id)
);

-- indexes
CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(text_hash);
CREATE INDEX IF NOT EXISTS idx_analyses_article ON analyses(article_id);