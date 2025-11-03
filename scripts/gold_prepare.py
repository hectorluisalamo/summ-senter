#!/usr/bin/env python3
import sqlite3, json, random, os
from collections import defaultdict

DB = 'data/app.db'
OUT = 'eval/gold_candidates.jsonl'
random.seed(42)

TARGET_EN = 30
TARGET_ES = 20
MAX_PER_DOMAIN = 20
POLICY = 'A'

os.makedirs('eval', exist_ok=True)
conn = sqlite3.connect(DB)
rows = conn.execute("""
    SELECT id, url, domain, lang, title FROM articles
    WHERE lang in ('en', 'es')
    ORDER BY create_time DESC
    LIMIT 500
""").fetchall()

by_lang = {'en': [], 'es': []}
for r in rows:
    by_lang[r[3]].append({'id': r[0], 'url': r[1], 'domain': r[2], 'lang': r[3], 'title': r[4] or ''})
    
def pick(items, k):
    random.shuffle(items)
    seen = defaultdict(int)
    out = []
    for i in items:
        if seen[i['domain']] >= MAX_PER_DOMAIN:
            continue
        out.append(i)
        seen[i['domain']] += 1
        if len(out) == k:
            break
    return out

picked = pick(by_lang['en'], TARGET_EN) + pick(by_lang['es'], TARGET_ES)
with open(OUT, 'w', encoding='utf-8') as f:
    for p in picked:
        f.write(json.dumps({
            **p,
            "reference_summary": "",
            "reference_sentiment": ""
        }, ensure_ascii=False) + "\n")
print(f'Wrote {len(picked)} candidates to {OUT} with policy={POLICY}')