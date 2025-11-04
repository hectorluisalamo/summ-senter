#!/usr/bin/env python3
import os, json, sqlite3, statistics
from scripts.sentiment_infer import predict_label
from scripts.summarize_openai import summarize
from scripts.eval_baselines import rouge_l_f
from bert_score import score as bertscore
from sklearn.metrics import f1_score

OFFLINE = os.getenv('SUMMARY_PROVIDER', 'openai') != 'openai'

GOLD = 'eval/gold_candidates.jsonl'
OUT_PATH = 'eval/model_metrics.json'
DB = 'data/app.db'

SUM_VER = 'rule:lead3@sum_stub' if OFFLINE else 'openai:gpt-5-mini@sum_v1'
SENT_VER = 'distilbert-mc@sent_v4'

BERT_MODEL = os.getenv('BERTSCORE_MODEL', 'roberta-base')

def load_gold():
    rows = []
    with open(GOLD, 'r', encoding='utf-8') as f:
        for line in f:
            rows.append(json.loads(line))
    return rows

def main():
    gold = load_gold()
    with sqlite3.connect(DB) as conn:
        idsnip = {r[0]: r[1] for r in conn.execute("SELECT id, snippet FROM articles").fetchall()}
        
        preds_summ, refs_summ = [], []
        sent_true, sent_pred = [], []
        
        for r in gold:
            text = idsnip.get(r['id'], '')
            if not text:
                continue
            summ = summarize(text, r['lang'])
            preds_summ.append(summ['summary'])
            refs_summ.append(r['reference_summary'])
            
            label, *_ = predict_label(text)
            sent_true.append(r['reference_sentiment'])
            sent_pred.append(label)
            
        rouge_scores = [rouge_l_f(ref, hyp) for ref, hyp in zip(refs_summ, preds_summ)]
        rouge_l_mean = float(statistics.mean(rouge_scores))
        P, R, F = bertscore(preds_summ, refs_summ, lang='en',
                            model_type=BERT_MODEL,
                            batch_size=16,
                            rescale_with_baseline=True,
                            verbose=False)
        bert_f1_mean = float(F.mean().item())
        macro = f1_score(sent_true, sent_pred, average='macro')
            
        results = {
            'summarization': {
                'rougeL_f_mean': round(rouge_l_mean, 4),
                'bertscore_f1_mean': round(bert_f1_mean, 4),
                'version': SUM_VER
            },
            'sentiment': {'macro_f1': round(macro, 4), 'version': SENT_VER}
        }
            
        os.makedirs('eval', exist_ok=True)
        with open(OUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
                
        print(json.dumps(results, indent=2))
            
if __name__ == '__main__':
    main()