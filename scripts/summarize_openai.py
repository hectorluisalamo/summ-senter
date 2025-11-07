#!/usr/bin/env python3
import os, time, re, textwrap
from openai import OpenAI
from scripts.translate_es_to_en import translate_es_to_en
from app.obs import log

PROMPT_PATH = 'prompts/summarize_v1.txt'
MODEL_NAME = os.getenv('SUMMARY_MODEL', 'gpt-5-mini')
VERSION = 'sum_v1'

MAX_TOKENS = int(os.getenv('SUMMARY_MAX_TOKENS', '300'))
MAX_PROMPT_CHARS = 4000

def _read_template(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()

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

def get_client() -> OpenAI:
    key = os.getenv('OPENAI_API_KEY', '')
    if not key:
        raise RuntimeError('OPENAI_API_KEY not set')
    return OpenAI(api_key=key)
    
def call_openai(prompt: str):
    client = get_client()
    messages = [
        {'role': 'system', 'content': 'You are a precise news summarizer. Neutral, faithful, 80-140 words.'},
        {'role': 'user', 'content': prompt}
    ]
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
    text, pt, ct = call_openai(prompt)
    dt = int((time.time() - t0) * 1000)
    return {
        'summary': text,
        'latency_ms': dt,
        'model_version': f'openai:{MODEL_NAME}@{VERSION}',
        'usage': {
            'prompt_tokens': pt,
            'completion_tokens': ct
        }
    }
    
if __name__ == '__main__':
    print(summarize("Officials raised rates by 25 bps, citing inflation pressures.", "en"))