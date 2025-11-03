#!/usr/bin/env python3
import sqlite3, json, random, os
from collections import Counter, defaultdict
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from langdetect import detect, LangDetectException
from sklearn.model_selection import train_test_split

try:
    from scripts.translate_es_to_en import translate_es_to_en
except Exception:
    translate_es_to_en = None
    
CFG = json.load(open('eval/sentiment_build_config.json'))
random.seed(CFG['seed']
            )
os.makedirs('models/sentiment', exist_ok=True)
DB = 'data/app.db'
GOLD = 'eval/gold_candidates.jsonl'
OUT = 'models/sentiment/dataset.jsonl'

def normalize_text(s: str) -> str:
    return ' '.join((s or '').split())

def is_english(s: str) -> bool:
    try:
        return detect(s)[:2] == 'en'
    except LangDetectException:
        return False
    
def ensure_english(text: str, lang: str) -> str:
    if translate_es_to_en and lang == 'es':
        return translate_es_to_en(text)
    return text
    
def cap_words(s: str, max_words: int) -> str:
    words = s.split()
    return ' '.join(words[:max_words])

def vader_label(compound: float, pos_thr: float, neg_thr: float) -> str:
    if compound >= CFG['vader_pos_thr']:
        return 'positive'
    if compound <= CFG['vader_neg_thr']:
        return 'negative'
    return 'neutral'

gold = []
gold_ids = set()
with open(GOLD, 'r', encoding='utf-8') as f:
    for line in f:
        r = json.loads(line)
        gold_ids.add(r['id'])
        text = normalize_text((r.get('title') or '') + ' ' + (r.get('reference_summary') or ''))
        text = cap_words(text, CFG['max_words'])
        gold.append({'text': text, 'label': r['reference_sentiment'], 'src': 'gold', 'id': r['id']})
        
# build pseudo-label pool from DB snippets (exclude gold ids to prevent leakage)
pool = []
with sqlite3.connect(DB) as conn:
    rows = conn.execute("SELECT id, snippet, lang FROM articles WHERE snippet IS NOT NULL LIMIT ?", (CFG['pseudo_pool_limit'],)).fetchall()
    analyzer = SentimentIntensityAnalyzer()
    for (aid, snip, lang) in rows:
        if aid in gold_ids:
            continue
        snip = normalize_text(snip or '')
        snip = ensure_english(snip, lang or '')
        if not snip:
            continue
        snip = cap_words(snip, CFG['max_words'])
        comp = analyzer.polarity_scores(snip)['compound']
        label = vader_label(comp, CFG['vader_pos_thr'], CFG['vader_neg_thr'])
        pool.append({'text': snip, 'label': label, 'src': 'pseudo', 'id': aid})

# balance pseudo set per label (stratified sampling)
by_label = defaultdict(list)
for ex in pool:
    by_label[ex['label']].append(ex)
    
target = CFG['pseudo_sample_target_per_label']
balanced = []
for label, bucket in by_label.items():
    random.shuffle(bucket)
    balanced.extend(bucket[:target])
    
# dedupe to avoid overlap
def dedupe(items):
    seen = set()
    out = []
    for ex in items:
        key = ex['text'].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(ex)
    return out

gold = dedupe(gold)
balanced = dedupe(balanced)

dataset = gold + balanced
labels = [ex['label'] for ex in dataset]


# train/val/test split (stratified)
train_val, test = train_test_split(dataset, test_size=CFG['split']['test'], random_state=CFG['seed'], stratify=labels)
tv_labels = [ex['label'] for ex in train_val]
train, val = train_test_split(train_val, test_size=CFG['split']['val'] / (1.0 - CFG['split']['test']),
                              random_state=CFG['seed'], stratify=tv_labels)

with open(OUT, 'w', encoding='utf-8') as f:
    for split, items in [('train', train), ('val', val), ('test', test)]:
        for ex in items:
            ex2 = {'text': ex['text'], 'label': ex['label'], 'split': split}
            f.write(json.dumps(ex2, ensure_ascii=False) + '\n')
            
# print histograms per split (visibility)
def hist(items):
    return dict(Counter([i['label'] for i in items]))
print('Counts:', {'train': len(train), 'val': len(val), 'test': len(test)})
print('Histograms:', {'train': hist(train), 'val': hist(val), 'test': hist(test)})