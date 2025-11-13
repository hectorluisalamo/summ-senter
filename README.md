# News Summarizer + Sentiment Analyzer :newspaper:

![Static Badge](https://img.shields.io/badge/License-MIT-blue)
![Static Badge](https://img.shields.io/badge/Built%20with-Python-green)
[![CI](https://github.com/hectorluisalamo/summ-senter/actions/workflows/ci.yml/badge.svg)](https://github.com/hectorluisalamo/summ-senter/actions/workflows/ci.yml)

Paste a URL or text (EN/ES). We translate (if ES), summarize (GPT-5 mini), classify tone (DistilBERT), and show cost+latency.

**Live demo:** <https://news-ui-imck.onrender.com> 
**API base:** <https://news-api-poev.onrender.com>

## Quickstart (local)
```bash
# API
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.api.txt requirements.ui.txt
uvicorn app.main:app --reload
# UI
streamlit run ui/app.py
```

## Architecture
```mermaid
flowchart LR
  A[Client/UI] -->|POST /analyze| B[API (FastAPI)]
  B --> C[Fetch & Clean]
  C --> D{lang}
  D -->|es| E[Opus-MT es→en]
  D -->|en| F[Pass-through]
  E --> G[GPT-5 mini • Summarize]
  F --> G
  G --> H[DistilBERT • Sentiment]
  H --> I[(SQLite/Postgres)]
  B --> J[(Redis Cache)]
  B --> K[/metrics + logs/]
  ```

## Metrics (current)
| **Variant** | **ROUGE-L(F)** | **BERTScore F1** | **Macro-F1 (sent)** | **p50 ms** | **p95 ms** | **Cost/1k toks (¢)** |
|-------------|----------------|------------------|---------------------|-----------|------------|----------------------|
| Baseline (Lead-3, VADER) | 0.186 | 0.8478 | 0.2675 | — | — | in:0.05/out:0.15 | — |
| Model v1 (gpt-5-mini@sum_v1, distilbert@sent_v2) | 0.2408 | 0.2995 | 0.2713 | — | — | in:0.05/out:0.15 | — |


## Limits
* Allowlist + robots.txt only.
* Summaries 80–140 words, neutral tone.
* Spanish is translated before summarization.
* Costs/latency displayed; cached repeats are faster.

## License
MIT (code). Respect publishers’ ToS; we store URLs + snippets only.

## Contributing

Pull requests and discussions are welcome.

Created and maintained by **Hector Luis Alamo**.  

📫 [LinkedIn](https://www.linkedin.com/in/hector-luis-alamo-90432941/)