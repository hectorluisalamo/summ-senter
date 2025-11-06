#!/usr/bin/env python3
import os, json, time, re, pathlib
from openai import OpenAI
from scripts.translate_es_to_en import translate_es_to_en
 
PROVIDER = os.getenv('SUMMARY_PROVIDER', 'openai')

client = OpenAI()

PROMPT_PATH = 'prompts/summarize_v1.txt'
model_name = os.getenv('SUMMARY_MODEL', 'gpt-5-mini')
VERSION = 'sum_v1'

MAX_TOKENS = int(os.getenv('SUMMARY_MAX_TOKENS', '200'))
TEMPERATURE = float(os.getenv('SUMMARY_TEMPERATURE', '0.1'))

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

def call_openai(prompt_text: str) -> str:
    client = OpenAI()

    messages = [
        {'role': 'system', 'content': 'You are a precise news summarizer. Neutral, faithful, 80-140 words.'},
        {'role': 'user', 'content': prompt_text}
    ]

    resp = client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE
    )
    text = resp.choices[0].message.content.strip()
    pt = resp.usage.prompt_tokens
    ct = resp.usage.completion_tokens
    return text, pt, ct
    
def build_prompt(article_text: str) -> str:
    with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
        template = f.read()
    return template + '\n\nARTICLE:\n' + article_text

def summarize(text: str, lang: str) -> dict:
    if lang == 'es':
        text = translate_es_to_en(text)
    text = ' '.join((text or '').split())[:4000]
    prompt = build_prompt(text)
    
    t0 = time.time()
    if PROVIDER == 'stub':
        out = lead_n_summary(text)[:140]
        mv = 'stub:lead3@sum_stub'
    elif PROVIDER == 'lead3':
        out = lead_n_summary(text)
        mv = 'rule:lead3@sum_rule'
    else:
        out, pt, ct = call_openai(prompt)
    dt_ms = int((time.time() - t0) * 1000)
    return {
        'summary': out,
        'latency_ms': dt_ms,
        'model_version': f'openai: {model_name}@{VERSION}',
        'usage': {
            'prompt_tokens': pt,
            'completion_tokens': ct
        } if PROVIDER not in ['stub', 'lead3'] else {}
    }
    
if __name__ == '__main__':
    print(summarize("Officials raised rates by 25 bps, citing inflation pressures.", "en"))