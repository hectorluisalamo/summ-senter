# Case Study — News Summarizer + Sentiment

## Problem
People need faithful summaries + tone in EN/ES with transparent costs and low latency.

## Users
Information workers and students.

## Constraint that shaped design
Legal/robots compliance (allowlist + robots.txt respected end to end).

## Design
- Pipeline: fetch → clean → translate (ES→EN) → summarize (GPT-5 mini) → sentiment (DistilBERT) → store → cache.  
- Caching uses **Postgres** (storage + response cache), avoiding a separate Redis service for a leaner footprint.

Allowlist (demo): cnn.com, foxnews.com, elmundo.es, lavanguardia.com, bbc.com.  
Sentiment target: **original text/snippet**, not the generated summary.

## Metrics
**Baseline (Lead-3 + VADER)**  
- ROUGE-L(F): 0.186  
- BERTScore F1: 0.8478 *(30 EN items, 20 ES; roberta-large)* 
- Macro-F1 (sent): 0.2675

**Model v1 (openai:gpt-5-mini@sum_v1 + distilbert-mc@sent_v4)**  
- ROUGE-L(F): 0.326  
- BERTScore F1: 0.894 *(30 EN items, 20 ES; roberta-large)*
- Macro-F1 (sent): 0.2713 (test)

Latency (warm path): p50 **~294 ms**, p95 **~380 ms** (Render).  
Typical cost per request: **1¢** for **~1456** tokens (input+output).

## Key ablations (what actually moved the needle)
**Summarizer**: longer prompt window improved ROUGE/BERTScore.  
**Sentiment**: widening the neutral band + **stratified sampling** helped most.  
**ES handling**: chose **translate-then-summarize** to standardize inputs and improve determinism.


## Ops (deploy & monitor)
- Deployed on **Render** as three services: API, UI, Postgres.  
- We log: `request_id, url, domain, lang, model_version, cache_hit, latency_ms, sum_latency_ms, prompt_tokens, completion_tokens, cost_cents`.  
- `/metrics` exposes counters and latency distributions (JSON).

## Incident & fix
Neutral was underrepresented in the gold/pseudo data, depressing macro-F1.  
**Fix**: widened neutral thresholds and stratified splits.  
**Outcome**: macro-F1 rose from ~0.26 → ~0.41 in intermediate runs; current test sits lower (0.27), so we’ll revisit data balance and class weighting.

## Links & versions
API: https://news-api-poev.onrender.com/  
UI:  https://news-ui-imck.onrender.com/  
Versions: `openai:gpt-5-mini@sum_v1`, `distilbert-mc@sent_v4`.

## Next 3 improvements
1) Better extractive highlights (TextRank/KeyBERT).  
2) Batched analysis for feeds; background jobs.  
3) DistilBERT v5 with more neutral examples + light domain adaptation.
