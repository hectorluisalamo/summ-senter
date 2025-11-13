#!/usr/bin/env python3
import argparse, os, json, sqlite3, statistics
from scripts.sentiment_infer import predict_label
from scripts.eval_baselines import rouge_l_f
from bert_score import score as bertscore
from sklearn.metrics import f1_score

OFFLINE = os.getenv('SUMMARY_PROVIDER', 'openai') != 'openai'

GOLD = 'eval/gold_candidates.jsonl'
OUT_PATH = 'eval/model_metrics.json'
DB_PATH = 'data/app.db'

SUM_VER = 'rule:lead3@sum_stub' if OFFLINE else 'openai:gpt-5-mini@sum_v1'
SENT_VER = 'distilbert-mc@sent_v4'

BERT_MODEL = os.getenv('BERTSCORE_MODEL', 'roberta-large')

def load_gold(path, lang_filter=None, max_items=None):
    rows = []
    with open(GOLD, 'r', encoding='utf-8') as f:
        for line in f:
            r  = json.loads(line)
            if lang_filter and r.get('lang') != lang_filter:
                continue
            rows.append(r)
            if max_items and len(rows) >= max_items:
                break
    return rows

def load_candidates(path):
    by_id = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            by_id[r['id']] = r['candidate']
    return by_id

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gold', default='eval/gold_candidates.jsonl')
    ap.add_argument('--out', default='eval/model_metrics.json')
    ap.add_argument('--lang', default='en')
    ap.add_argument('--max_items', type=int, default=20)
    ap.add_argument('--cands_path', default=None) # If set, skip summarizer
    args =ap.parse_args()
    
    gold = load_gold(args.gold, lang_filter=args.lang, max_items=args.max_items)
    
    # --- Either load candidates or generate them (skip API if cands provided) ---
    if args.cands_path:
        cands_by_id = load_candidates(args.cands_path)
        cands = [cands_by_id[g['id']] for g in gold if g['id'] in cands_by_id]
        refs = [g['reference_summary'] for g in gold if g['id'] in cands_by_id]
    else:
        from scripts.summarize_openai import summarize
        cands, refs = [], []
        for g in gold:
            text = g.get('text') or g.get('article_text') or ''
            out = summarize(text, g['lang'])
            cands.append(out['summary'])
            refs.append(g['reference_summary'])
            
    P, R, F1 = bertscore(
        cands, refs,
        lang='en',
        model_type=BERT_MODEL,
        batch_size=16,
        rescale_with_baseline=True,
        verbose=False
    )
    bert_f1_mean = float(F1.mean())
            
    results = {
        'summarization': {
            'bertscore_f1_mean': bert_f1_mean,
            'version': SUM_VER
        },
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(results, f, indent=2)
    print('Wrote', args.out, 'with BERTScore F1 =', round(bert_f1_mean, 4))
            
if __name__ == '__main__':
    main()