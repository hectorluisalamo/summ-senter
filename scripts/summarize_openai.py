#!/usr/bin/env python3
import os, time, re
from openai import OpenAI
from scripts.translate_es_to_en import translate_es_to_en
 
PROVIDER = os.getenv('SUMMARY_PROVIDER', 'openai')

client = OpenAI()

PROMPT_PATH = 'prompts/summarize_v1.txt'
model_name = os.getenv('SUMMARY_MODEL', 'gpt-5-mini')
VERSION = 'sum_v1'

max_tokens = int(os.getenv('SUMMARY_MAX_TOKENS', '200'))
temp = float(os.getenv('SUMMARY_TEMPERATURE', '1'))

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
        max_completion_tokens=max_tokens,
        temperature=temp
    )
    text = resp.choices[0].message.content.strip()
    pt = resp.usage.prompt_tokens
    ct = resp.usage.completion_tokens
    return text, pt, ct
    
def build_prompt(article_text: str, title: str = '', lede: str = '') -> str:
    with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
        instructions = f.read()
        context = ''
        if title:
            context += f'TITLE: {title}\n'
        if lede:
            context += f'LEDE: {lede}\n'
    return instructions + '\n' + context + '\n' + 'ARTICLE:\n' + article_text

def sentence_case(text: str) -> str:
    def sent_split():
        re.compile(r'([.!?]\s+)')
    parts = sent_split((text or '').strip())
    out = []
    for i in range(0, len(parts), 2):
        sent = parts[i]
        sep = parts[i+1] if i+1 < len(parts) else ''
        sent = sent[:1].upper() + sent[1:]
        out.append(sent + sep)
    return ''.join(out)

def inject_subject_if_missing(summary: str, title: str) -> str:
    title_norm = title.title() if title and title.isupper() else title or ''
    matches = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', title_norm or '')
    name = matches[0] if matches else ''
    first_sent = re.split(r'(?<=[.!?])\s+', summary, maxsplit=1)[0]
    pattern = re.compile(rf'\b{re.escape(name)}\b', flags=re.IGNORECASE)
    if name and not pattern.search(first_sent):
        return f'{name}: {summary}'
    return summary

def summarize(text: str, lang: str, title: str = '', lede: str = '') -> dict:
    if lang == 'es':
        text = translate_es_to_en(text)
    text = ' '.join((text or '').split())[:4000]
    prompt = build_prompt(text, title=title, lede=lede)
    t0 = time.time()
    if PROVIDER == 'stub':
        out = lead_n_summary(text)[:140]
        out = sentence_case(out)
        out = inject_subject_if_missing(out, title)
        mv = 'stub:lead3@sum_stub'
    elif PROVIDER == 'lead3':
        out = lead_n_summary(text)
        out = sentence_case(out)
        out = inject_subject_if_missing(out, title)
        mv = 'rule:lead3@sum_rule'
    else:
        out, pt, ct = call_openai(prompt)
        out = sentence_case(out)
        out = inject_subject_if_missing(out, title)
    dt = int((time.time() - t0) * 1000)
    return {
        'summary': out.strip(),
        'latency_ms': dt,
        'model_version': f'openai: {model_name}@{VERSION}',
        'usage': {
            'prompt_tokens': pt,
            'completion_tokens': ct
        } if PROVIDER not in ['stub', 'lead3'] else {}
    }
    
if __name__ == '__main__':
    print(summarize("Officials raised rates by 25 bps, citing inflation pressures.", "en"))