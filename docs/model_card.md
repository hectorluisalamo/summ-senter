# Model Card — News Summarizer + Sentiment Analyzer

## Intended Use
- Summarize news (EN/ES via ES→EN translation) into 80–140 words.
- Classify article tone: positive/neutral/negative (framing, not morality).

## Models
- Summarizer: openai:gpt-5-mini@sum_v1 (prompted; deterministic).
- Translator: Helsinki-NLP/opus-mt-es-en.
- Sentiment: distilbert-base-multilingual-cased fine-tuned on gold+pseudo (v2).

## Data
- Gold set: 50 articles (30 EN / 20 ES). Policy A (English references).
- Pseudo labels: ~N snippets with VADER; stratified per label; EN-only/translated.

## Metrics (gold set)
- ROUGE-L(F): 0.186 ; BERTScore F1: 0.8478 ; Macro-F1: 0.2675 (test).
- Baseline deltas: +0.05 ROUGE-L ; +0.10 Macro-F1.

## Limitations
- VADER pseudo-labeling may bias neutral upward; model can overfit wire-style writing.
- Spanish translation errors can shift sentiment subtly.
- Summarizer can omit minority views under strict length targets.

## Ethical Considerations
- Respect robots.txt; store snippets not full text for restricted sources.
- Tone classification can reflect source/political bias; provide confidence and model version.

## Versioning
- Summarizer: gpt-5-mini@sum_v1; Sentiment: distilbert-mc@sent_v24; Prompt v1 in `prompts/`.
