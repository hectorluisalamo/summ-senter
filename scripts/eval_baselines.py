#!/usr/bin/env python3
import os, json, re, sqlite3, statistics
from typing import List

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.metrics import f1_score, classification_report
from rouge_score import rouge_scorer
from bert_score import score as bertscore

DB_PATH = 'data/app.db'
GOLD = 'eval/gold_candidates.jsonl'
OUT_JSON = 'eval/baseline_metrics.json'
OUT_TABLE = 'eval/baseline_metrics.txt'
CFG = json.load(open('eval/config.json'))

def lead_n_summary(text: str, n: int, max_words: int) -> str:
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    take = sents[:n]
    words = []
    for s in take:
        for w in s.split():
            if len(words) < max_words:
                words.append(w)
    return ' '.join(words)

def vader_label(compound: float, pos_thr: float, neg_thr: float) -> str:
    if compound >= pos_thr: return 'positive'
    if compound <= neg_thr: return 'negative'
    return 'neutral'

def macro_f1(y_true: List[str], y_pred: List[str]) -> float:
    return f1_score(y_true, y_pred, average='macro')

def rouge_l_f(ref: str, hyp: str) -> float:
    ref = (ref or '').strip()
    hyp = (hyp or '').strip()
    if not ref or not hyp:
        return 0.0
    scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
    res = scorer.score(ref, hyp)
    return res['rougeL'].fmeasure

def load_gold() -> List[dict]:
    rows = []
    with open(GOLD, 'r', encoding='utf-8') as f:
        for line in f:
            rows.append(json.loads(line))
    assert len(rows) == 50
    return rows

def attach_snippets(rows: List[dict]) -> List[dict]:
    conn = sqlite3.connect(DB_PATH)
    id2snip = {r[0]: r[1] for r in conn.execute(
        "SELECT id, snippet FROM articles"
    ).fetchall()}
    for r in rows:
        r['snippet'] = id2snip.get(r['id'], '')
    return rows

def main():
    gold = attach_snippets(load_gold())
    lead_n = CFG['lead_n_sentences']
    lead_cap = CFG['lead_max_words']
    preds_summ = []
    refs_summ = []
    
    for r in gold:
        text = r.get('snippet', '') or ''
        hyp = lead_n_summary(text, lead_n, lead_cap)
        refs_summ.append(r['reference_summary'])
        preds_summ.append(hyp)
        
    # ROUGE-L (F) per item
    rouge_scores = [rouge_l_f(ref, hyp) for ref, hyp in zip(refs_summ, preds_summ)]
    rouge_l_mean = float(statistics.mean(rouge_scores))
    
    # BERTScore F1
    P, R, F = bertscore(preds_summ, refs_summ, model_type='roberta-large')
    bert_f1_mean = float(F.mean().item())
    
    # Sentiment baseline: VADER on snippet
    analyzer = SentimentIntensityAnalyzer()
    y_true, y_pred = [], []
    for r in gold:
        y_true.append(r['reference_sentiment'])
        v_score = analyzer.polarity_scores(r.get('snippet', '') or '')
        v_label = vader_label(v_score['compound'], CFG['vader_pos'], CFG['vader_neg'])
        y_pred.append(v_label)
        
    macro = macro_f1(y_true, y_pred)
    report = classification_report(y_true, y_pred, digits=3, zero_division=0)
    
    results = {
        'counts': {'n': len(gold)},
        'config': CFG,
        'summarization': {
            'rougeL_f_mean': round(rouge_l_mean, 4),
            'bertscore_f1_mean': round(bert_f1_mean, 4)
        },
        'sentiment': {
            'macro_f1': round(macro, 4),
            'report': report
        },
        'gate': {
            'target_improvement': {
                'rougeL': 0.05,
                'macroF1': 0.10
            }
        }
    }
    
    os.makedirs('eval', exist_ok=True)
    with open(OUT_JSON, 'w') as f:
        json.dump(results, f, indent=2)
    with open(OUT_TABLE, 'w') as f:
        f.write(
            f'Baseline (Lead-{lead_n} @ {lead_cap}w, VADER)\n'
            f'ROUGE-L (F) mean: {results['summarization']['rougeL_f_mean']}\n'
            f'BERTScore F1 mean: {results['summarization']['bertscore_f1_mean']}\n'
            f'sentiment macro-F1: {results['sentiment']['macro_f1']}\n\n'
            f'{report}\n'
        )
    print('Saved:', OUT_JSON, 'and', OUT_TABLE)
    
if __name__ == '__main__':
    main()