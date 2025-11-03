Title:
News Summarizer + Sentiment

Problem:
Information workers drown in articles. Need faithful, concise summaries and sentiment with transparent sources (EN/ES) at low cost.

Users:
Info workers, students, journalists

In-Scope:
- RSS ingest (allowlist) with robots.txt compliance
- HTML sanitize, dedupe, language detection (EN/ES)
- ES→EN translate → summarize with OpenAI GPT-5 mini (token-capped)
- Sentiment via DistilBERT (multilingual) fine-tuned on project labels
- API + Streamlit UI; show key sentences, tokens, latency, cost

Out-of-Scope (v1):
- Broad scraping/paywalls; per-user auth; topic clustering.

Success Metrics:
- Summaries: ROUGE-L ≥ 0.30; BERTScore F1 ≥ 0.85; human rubric ≥ 4/5.
- Sentiment: macro-F1 ≥ 0.80 overall and per-language.
- Latency p95: ≤ 2.0s (cached) / ≤ 6.0s (cold).
- Cost ≤ $15/mo; uptime ≥ 99%.

Data/Storage:
- Service DB: SQLite (dev) → Postgres (prod).
- Analytics: DuckDB files for evals/plots.
- Store URLs + metadata + snippets/embeddings; avoid full-text where restricted.

APIs:
POST /analyze { url|html|text, lang? } → { id, summary, key_sentences, sentiment, confidence, tokens, latency_ms, costs_cents, model_version, cache_hit }
GET /article/:id → { article, analyses }
POST /feedback { id, rating, notes? } → { ok }
GET /health → { status }
GET /metrics → { counters, histograms }

Risks & Mitigations:
- Legal/ToS: RSS-only + allowlist; robots.txt honored; store URLs/snippets; purge on request.
- Prompt injection/XSS: sanitize HTML; strip scripts/iframes/styles/events; escape outputs; input caps.
- Translation artifacts: cap length; mark quotes; evaluate per-lang; error analysis loop.
- Bias (EN/ES): stratified gold set; per-language F1; confusion matrices.
- Cost spikes: Redis cache (72h); strict token caps; rate limits; monthly budget alarms.
- Reliability: timeouts; retries/backoff; per-domain circuit breaker; dead-letter for failures.

Milestones:
M0: Baselines + eval on 50-item gold set (DuckDB notebook).  
M1: Live API + UI on Render with /metrics.  
M2: Case study + promo assets.

Definition of Done:
Live UI+API; CI tests pass; metrics panel shows p95 + $/article; case study published.
