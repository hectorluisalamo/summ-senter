#!/usr/bin/env python3
import os, time, re, textwrap
from openai import OpenAI
from scripts.translate_es_to_en import translate_es_to_en
from app.obs import log
 
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

def call_openai(prompt: str) -> str:
    client = OpenAI()

    messages = [
        {'role': 'system', 'content': 'You are a precise news summarizer. Neutral, faithful, 80-140 words.'},
        {'role': 'user', 'content': prompt}
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

def sentence_case(text: str) -> str:
    s = (text or '').strip()
    if not s:
        return s
    parts = _SENT_BREAK.split(s)
    fixed = []
    for sent in parts:
        m = re.match(r"^([\(\[\{\'\"“”‘’]+)?(.*)$", sent)
        lead = m.group(1) or ''
        body = m.group(2) or ''
        for i, ch, in enumerate(body):
            if ch.isalpha():
                body = body[:i] + ch.upper() + body[i+1:]
                break
        fixed.append(lead + body)
    return ''.join(fixed)

def inject_subject_if_missing(summary: str, title: str) -> str:
    s = (summary or '').strip()
    if not s:
        return s
    first_sent = s.split(".",1)[0].strip()
    if not first_sent:
        return s
    m = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', title or '')
    name = m[0] if m else ''
    if name and name.lower() not in first_sent.lower():
        return f'{name} {first_sent[0].lower() + first_sent[1:]}.' + ('' if '.' not in s else ' ' + s.split('.', 1)[1].strip())
    return s

def tidy_summary(s: str) -> str:
    s = (s or '').strip()
    s = re.sub(r':\s*$', '.', s)
    s = re.sub(r'(\bin\s+[A-Z][a-z]+)\s*:\s*', r'\1, ', s)
    s = re.sub(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+):\s+\1\b', r'\1', s)
    
    # If text ends mid-sentence or lacks ending punc, trim to last full stop
    if s.count('"') % 2 == 1 or s.count('"') != s.count('"'):
        s = re.split(r'(?<=[.!?])\s', s)[0]
        
    if not re.search(r'[.!?]["”\']?\s*$', s):
        s = s.rstrip(' :—-') + '.'
    return s

def summarize(text: str, lang: str, title: str = '', lede: str = '') -> dict:
    if lang == 'es':
        text = translate_es_to_en(text)
    lede = normalize_lede(lede)
    prompt = build_prompt(trim_article(text), title=title, lede=lede)
    t0 = time.time()
    out, pt, ct = call_openai(prompt)
    out = sentence_case(out)
    out = inject_subject_if_missing(out, title)
        
    # Hard guarantee; never return nothing
    if not good_enough(out):
        try:
            reprompt = (
                'Write exactly 3 sentences (≈90-110 words).'
                'Sentence 1 must state who did what.'
                'Include the named subject from TITLE if present.\n\n'
            ) + prompt
            out2, pt2, ct2 = call_openai(reprompt)
            out2 = inject_subject_if_missing(sentence_case(out2), title)
            if good_enough(out2):
                out, pt, ct = out2, pt+pt2, ct+ct2
        except Exception:
            pass
    if not good_enough(out):
        out = extractive_fallback(title, lede, text)
    
    out = tidy_summary(out)    
    dt = int((time.time() - t0) * 1000)
    return {
        'summary': out.strip(),
        'latency_ms': dt,
        'model_version': f'openai: {model_name}@{VERSION}',
        'usage': {
            'prompt_tokens': pt,
            'completion_tokens': ct}
    }
    
if __name__ == '__main__':
    print(summarize("Officials raised rates by 25 bps, citing inflation pressures.", "en"))