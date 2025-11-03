#!/usr/bin/env python3
import os, torch, json
from typing import List, Tuple
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

vader = SentimentIntensityAnalyzer()

CKPT_DIR = 'ckpts/distilbert-mc_sent_v4'
MODEL_VERSION = 'distilbert-mc@sent_v4'
MAX_LEN = 256
CFG = json.load(open('eval/sentiment_build_config.json'))

UNCERTAIN_MAXP = 0.55
VADER_POS = CFG['vader_pos_thr']
VADER_NEG = CFG['vader_neg_thr']

device = 'cuda' if torch.cuda.is_available() else 'cpu'
tokenizer = AutoTokenizer.from_pretrained(CKPT_DIR)
model = AutoModelForSequenceClassification.from_pretrained(CKPT_DIR).to(device).eval()
ID2LABEL = model.config.id2label if hasattr(model.config, 'id2label') else {0: 'negative', 1: 'neutral', 2: 'positive'}

def _normalize(text: str) -> str:
    return ' '.join((text or '').split())

@torch.inference_mode()
def predict_label(text: str) -> Tuple[str, float, str]:
    text = _normalize(text)
    batch = tokenizer(text, return_tensors='pt', truncation=True, max_length=MAX_LEN)
    batch = {k: v.to(device) for k, v in batch.items()}
    
    logits = model(**batch).logits.squeeze(0)
    probs = torch.softmax(logits, dim=-1).detach().cpu()
    pid = int(probs.argmax().item())
    maxp = float(probs[pid].item())
    label = ID2LABEL.get(pid, 'neutral')
    
    # fallback if unsure
    if maxp < UNCERTAIN_MAXP:
        comp = vader.polarity_scores(text)['compound']
        if comp >= VADER_POS:
            label, maxp = 'positive', max(maxp, float(comp))
        elif comp <= VADER_NEG:
            label, maxp = 'negative', max(maxp, float(abs(comp)))
    
    return label, float(maxp), MODEL_VERSION

@torch.inference_mode()
def predict_batch(texts: List[str]) -> List[Tuple[str, float, str]]:
    texts = [_normalize(t) for t in texts]
    enc = tokenizer(texts, return_tensors='pt', truncation=True, padding=True, max_length=MAX_LEN)
    enc = {k: v.to(device) for k, v in enc.items()}
    logits = model(**enc).logits
    probs = torch.softmax(logits, dim=-1)
    ids = probs.argmax(dim=-1).detach().cpu().tolist()
    confs = probs.max(dim=-1).values.detach().cpu().tolist()
    return [(ID2LABEL[i], float(c), MODEL_VERSION) for i, c in zip(ids, confs)]

if __name__ == '__main__':
    print(predict_label('The outlook remains uncertain; oficials urged caution.'))
    print(predict_batch(['Profits jump to a record.', 'Critics blasted the move as reckless.']))