CREATE TABLE gold_articles(
    article_id TEXT PRIMARY KEY,
    url TEXT,
    domain TEXT,
    lang TEXT,
    title TEXT,
    reference_summary TEXT,     -- human 120-200 words
    reference_sentiment TEXT    -- pos/neg/neutral
);

CREATE TABLE runs(
    run_id TEXT,
    model_version TEXT,         -- "openai:gpt-5-mini@pX | sent:distilbert@ckptY"
    create_time TIMESTAMP
);

CREATE TABLE outputs(
    run_id TEXT,
    article_id TEXT,
    system_summary TEXT,
    system_sentiment TEXT,
    system_confidence DOUBLE,
    tokens, INTEGER,
    latency_ms INTEGER
);

CREATE TABLE metrics(
    run_id TEXT,
    article_id TEXT,
    rouge_l DOUBLE,
    bertscore_f1 DOUBLE,
    sentiment_correct INTEGER
);

CREATE INDEX idx_outputs_run ON outputs(run_id);
CREATE INDEX idx_metrics_run ON metrics(run_id);