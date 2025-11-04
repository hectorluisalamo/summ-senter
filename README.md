# News Summarizer + Sentiment :open_book:

![CI](https://github.com/hectorluisalamo/summ-senter/actions/workflows/ci.yml/badge.svg)

Fast, faithful news summaries with sentiment, English/Spanish support, a minimal API, and a growing eval suite. Built to be **cheap, legal, and reproducible**.

> Status: step 7/13 – service live on Render, tests & CI in place, baseline + early model evals done.

---

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Setup](#setup)
- [Configuration](#configuration)
- [Running Locally](#running-locally)
- [Data Pipeline](#data-pipeline)
- [API](#api)
- [Storage Schema](#storage-schema)
- [Evaluation & Metrics](#evaluation--metrics)
- [Testing & CI](#testing--ci)
- [Deployment](#deployment)
- [Security & Legal](#security--legal)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

---

## Features
- **Summaries**: concise, neutral, 80–140 words, with optional key-sentence highlights.
- **Sentiment**: `positive | neutral | negative` with confidence.
- **Bilingual**: ES→EN translation before summarization; EN handled natively.
- **Explainability**: links back to sources; (highlights coming in Step 9).
- **Caching**: Redis (optional) to hit cost/latency targets.
- **API-first**: FastAPI service; UI planned (Streamlit).
- **Eval suite**: 50-item gold set, baselines, offline gate, CI.

---

## Architecture
- RSS/URL → fetch → clean/sanitize → (ES→EN) → summarize (LLM) → sentiment (DistilBERT)
- store metadata/snippet → SQLite/Postgres
- cache (Redis, 72h)
