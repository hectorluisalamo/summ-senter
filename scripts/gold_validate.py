#!/usr/bin/env python3
import json, sys, re

GOLD_JSON = 'eval/gold_candidates.jsonl'
langs = {'en', 'es'}
sents = {'positive', 'neutral', 'negative'}

ids, urls, en, es, bad = set(), set(), 0, 0, 0
with open(GOLD_JSON, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        try:
            r = json.loads(line)
        except Exception:
            print(f'Line {i}: not valid JSON'); bad+=1; continue
        for k in ['id', 'url', 'domain', 'lang', 'title', 'reference_summary', 'reference_sentiment']:
            if k not in r or r[k] in (None, ''):
                print(f'Line {i}: missing{k}'); bad+=1
            if r.get('lang') not in langs:
                print(f'Line {i}: bad lang {r.get('lang')}'); bad+=1
            if r.get('reference_sentiment') not in sents:
                print(f'Line {i}: bad sentiment {r.get('reference_sentiment')}'); bad+=1
            if len(r.get('reference_summary', '').split()) < 30:
                print(f'Line {i}: summary too short (<30 words)'); bad+=1
            ids.add(r['id']); urls.add(r['url'])
            en += (r['lang']=='en'); es += (r['lang']=='es')

print(f'Totals: {len(ids)} items | EN={en} ES={es} | bad={bad}')
if len(ids)!=50: print ('Need exactly 50 items.')
if not (en==30 and es==20): print('Must be EN=30, ES=20')