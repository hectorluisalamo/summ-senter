#!/usr/bin/env python3
import os, json, time, re, pathlib
from openai import OpenAI
from scripts.translate_es_to_en import translate_es_to_en

client = OpenAI()

PROMPT_PATH = 'prompts/summarize_v1.txt'
MODEL_NAME = os.getenv('SUMMARY_MODEL', 'gpt-5-mini')
VERSION = 'sum_v1'

MAX_TOKENS = int(os.getenv('SUMMARY_MAX_TOKENS', '200'))
TEMPERATURE = float(os.getenv('SUMMARY_TEMPERATURE', '0.1'))

def call_openai(prompt_text: str) -> str:
    from openai import OpenAI
    client = OpenAI()

    messages = [
        {'role': 'system', 'content': 'You are a precise news summarizer. Neutral, faithful, 80-140 words.'},
        {'role': 'user', 'content': prompt_text}
    ]

    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE
    )
    return resp.choices[0].message.content.strip()
    
def build_prompt(article_text: str) -> str:
    with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
        template = f.read()
    return template + '\n\nARTICLE:\n' + article_text

def summarize(text: str, lang: str) -> dict:
    if lang == 'es':
        text = translate_es_to_en(text)
    text = ' '.join((text or '').split())[:4000]
    prompt_text = build_prompt(text)
    t0 = time.time()
    out = call_openai(prompt_text)
    dt_ms = int((time.time() - t0) * 1000)
    return {
        'summary': out,
        'latency_ms': dt_ms,
        'model_version': f'openai: {MODEL_NAME}@{VERSION}'
    }
    
if __name__ == '__main__':
    print(summarize("Officials raised rates by 25 bps, citing inflation pressures.", "en"))