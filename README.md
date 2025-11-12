# News Summarizer + Sentiment Analyzer :newspaper:

![Static Badge](https://img.shields.io/badge/License-MIT-blue)
![Static Badge](https://img.shields.io/badge/Built%20with-Python-green)
[![CI](https://github.com/hectorluisalamo/summ-senter/actions/workflows/ci.yml/badge.svg)](https://github.com/hectorluisalamo/summ-senter/actions/workflows/ci.yml)

Fast, faithful news summaries with sentiment analysis, English/Spanish support, a minimal API, and a growing evaluation suite. Built to be **cheap, legal, and reproducible**.

> Status: step 9/13 – service live on Render, tests & CI in place, baseline + early model evals done.

## Features
- **Summaries**: concise, neutral, 80–140 words, with optional key-sentence highlights.
- **Sentiment**: `positive | neutral | negative` with confidence.
- **Bilingual**: ES→EN translation before summarization; EN handled natively.
- **Explainability**: links back to sources; (highlights coming in Step 9).
- **Caching**: Postgres cache for solo app with low QPS
- **API-first**: FastAPI service; UI planned (Streamlit).
- **Eval suite**: 50-item gold set, baselines, offline gate, CI.
