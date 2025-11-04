#!/usr/bin/env python3
import os, torch, json
from typing import List, Tuple
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

vader = SentimentIntensityAnalyzer()

CKPT_REPO = 'hugger2484/distilbert-mc-sent-v4'
MODEL_VERSION = 'distilbert-mc@sent_v4'
MAX_LEN = 256
CFG = json.load(open('eval/sentiment_build_config.json'))

UNCERTAIN_MAXP = 0.55
VADER_POS = CFG['vader_pos_thr']
VADER_NEG = CFG['vader_neg_thr']

_device = 'cuda' if torch.cuda.is_available() else 'cpu'
_hf_token = os.getenv('HUGGINGFACE_HUB_TOKEN')
_tokenizer = None
_model = None

def _normalize(text: str) -> str:
    return ' '.join((text or '').split())

def _load_once():
    global _tokenizer, _model
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(CKPT_REPO, use_auth_token=_hf_token)
    if _model is None:
        _model = AutoModelForSequenceClassification.from_pretrained(CKPT_REPO, use_auth_token=_hf_token).to(_device).eval()
    return _tokenizer, _model

@torch.inference_mode()
def predict_label(text: str) -> Tuple[str, float, str]:
    tokenizer, model = _load_once()
    text = _normalize(text)
    batch = tokenizer(text, return_tensors='pt', truncation=True, max_length=MAX_LEN)
    batch = {k: v.to(_device) for k, v in batch.items()}
    
    logits = model(**batch).logits.squeeze(0)
    probs = torch.softmax(logits, dim=-1).detach().cpu()
    pid = int(probs.argmax().item())
    maxp = float(probs[pid].item())
    id2label = model.config.id2label if hasattr(model.config, 'id2label') else {0: 'negative', 1: 'neutral', 2: 'positive'}
    label = id2label.get(pid, 'neutral')
    
    # Fallback if unsure
    if maxp < UNCERTAIN_MAXP:
        comp = vader.polarity_scores(text)['compound']
        if comp >= VADER_POS:
            label, maxp = 'positive', max(maxp, float(comp))
        elif comp <= VADER_NEG:
            label, maxp = 'negative', max(maxp, float(abs(comp)))
    
    return label, float(maxp), MODEL_VERSION

@torch.inference_mode()
def predict_batch(texts: List[str]) -> List[Tuple[str, float, str]]:
    tokenizer, model = _load_once()
    texts = [_normalize(t) for t in texts]
    enc = tokenizer(texts, return_tensors='pt', truncation=True, padding=True, max_length=MAX_LEN)
    enc = {k: v.to(_device) for k, v in enc.items()}
    logits = model(**enc).logits
    probs = torch.softmax(logits, dim=-1)
    ids = probs.argmax(dim=-1).detach().cpu().tolist()
    confs = probs.max(dim=-1).values.detach().cpu().tolist()
    id2label = model.config.id2label if hasattr(model.config, 'id2label') else {0: 'negative', 1: 'neutral', 2: 'positive'}
    return [(id2label[i], float(c), MODEL_VERSION) for i, c in zip(ids, confs)]

if __name__ == '__main__':
    print(predict_label('The outlook remains uncertain; oficials urged caution.'))
    print(predict_batch(['Profits jump to a record.', 'Critics blasted the move as reckless.']))