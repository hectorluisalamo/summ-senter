#!/usr/bin/env python3
import os, time, re
from scripts.translate_es_to_en import translate_es_to_en
from app.obs import log

PROVIDER = os.getenv('SUMMARY_PROVIDER,' 'openai')

MODEL_NAME = os.getenv('SUMMARY_MODEL', 'gpt-5-mini')
VERSION = 'sum_v1'

MAX_TOKENS = int(os.getenv('SUMMARY_MAX_TOKENS', '300'))
MAX_PROMPT_CHARS = 4000

def lead_n_summary(text: str, n: int = 3, max_words: int = 180) -> str:
    s = ' '.join((text or '').split())
    if not s:
        return ''
    sents = re.split(r'(?<=[.!?])\s+', s)
    take = sents[:n] if sents else [s]
    words = []
    for sent in take:
        for w in sent.split():
            if len(words) < max_words:
                words.append(w)
    return ' '.join(words)

def trim_article(text: str) -> str:
    s = (text or '').strip()
    parts = re.split(r'(?<=[.!?])\s+', s)
    s = ' '.join(parts[:10])
    return s[:MAX_PROMPT_CHARS]

def build_prompt(article_text: str, title: str = '', lede: str = '') -> str:
    instructions = [
        'You are a precise news summarizer.\n' 
        'Write neutral, faithful, 80-140 words, 3-4 sentences.\n' 
        'First sentence must state the main event plainly, including the subject(s) by name if known (from title/lede).\n'
        'In the second sentence, provide essential details, including key figures, people, locations, dates, etc.\n'
        'In the remaining sentence(s), provide further context (e.g., what will happen next).\n'
        'Use standard capitalization and punctuation.\n'
        'Do not give your own opinions.\n'
        'Return only the summary text.'
    ]
    return f'{instructions}\n\nARTICLE:\n{trim_article(article_text)}'
    
def call_openai(prompt: str):
    try:
        from openai import OpenAI
    except Exception:
        return '<stub summary', 0, 0
    client = OpenAI()
    response = client.responses.create(
        model=MODEL_NAME,
        input=prompt
    )
    text = response.output_text
    pt = response.usage.input_tokens
    ct = response.usage.output_tokens
    return text, pt, ct

def summarize(text: str, lang: str) -> dict:
    if lang == 'es':
        text = translate_es_to_en(text)
    text = ' '.join((text or '').split())[:4000]
    prompt = build_prompt(text)
    t0 = time.time()
    if PROVIDER in ('lead3', 'stub'):
        out = lead_n_summary(text)
        return {'summary': out, 'latency_ms': 0, 'model_version': 'rule:lead3@sum_stub'}
    else:
        mv = f"openai:{MODEL_NAME}@{VERSION}"
        out, pt, ct = call_openai(prompt)
        dt = int((time.time() - t0) * 1000)
        return {
        'summary': out,
        'latency_ms': dt,
        'model_version': mv,
        'usage': {
            'prompt_tokens': pt,
            'completion_tokens': ct
        }
    }
    
if __name__ == '__main__':
    print(summarize("Officials raised rates by 25 bps, citing inflation pressures.", "en"))