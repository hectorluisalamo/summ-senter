#!/usr/bin/env python3
import os, torch, json
from typing import List, Tuple
from transformers import AutoTokenizer, AutoModelForSequenceClassification
CKPT_REPO = 'hugger2484/distilbert-mc-sent-v4'
mv = 'distilbert-mc@sent_v4'
MAX_LEN = 256
CFG = json.load(open('eval/sentiment_build_config.json'))

UNCERTAIN_MAXP = 0.55
VADER_POS = CFG['vader_pos_thr']
VADER_NEG = CFG['vader_neg_thr']

_device = 'cuda' if torch.cuda.is_available() else 'cpu'
_hf_token = os.getenv('HUGGINGFACE_HUB_TOKEN')
_tokenizer = None
_model = None
ID2LABEL = {0: "negative", 1: "neutral", 2: "positive"}

def _coerce_to_text(x) -> str:
    if isinstance(x, str):
        return x
    if isinstance(x, (list, tuple)):
        try:
            return ' '.join([str(t) for t in x])
        except Exception:
            return ' '.join(map(str, x))
    return str(x)

def _normalize(text: str) -> str:
    return ' '.join((text or '').split())

def _load_once():
    global _tokenizer, _model
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained(CKPT_REPO, token=_hf_token)
    if _model is None:
        _model = AutoModelForSequenceClassification.from_pretrained(CKPT_REPO, token=_hf_token).to(_device).eval()
    return _tokenizer, _model

@torch.inference_mode()
def predict_label(text: str) -> Tuple[str, float, str]:
    tokenizer, model = _load_once()
    text = _coerce_to_text(text)
    text = _normalize(text)
    batch = tokenizer(text, return_tensors='pt', truncation=True, max_length=MAX_LEN)
    batch = {k: v.to(_device) for k, v in batch.items()}
    
    logits = model(**batch).logits.squeeze(0)
    probs = torch.softmax(logits, dim=-1).detach().cpu()
    p_neg, p_neu, p_pos = probs.tolist()
    pid = int(probs.argmax().item())
    maxp = float(probs[pid].item())
    id2label = model.config.id2label if hasattr(model.config, 'id2label') else {0: 'negative', 1: 'neutral', 2: 'positive'}
    label = id2label.get(pid, 'neutral')
    
    TAU = 0.4
    DELTA = 0.08
    
    if maxp < TAU:
        return 'neutral', maxp, mv
    
    if abs(p_pos - p_neg) < DELTA and p_neu >= min (p_pos, p_neg):
        return 'neutral', float(p_neu), mv
    
    return label, float(maxp), mv

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
    return [(id2label[i], float(c), mv) for i, c in zip(ids, confs)]

if __name__ == '__main__':
    print(predict_label('The outlook remains uncertain; oficials urged caution.'))
    print(predict_batch(['Profits jump to a record.', 'Critics blasted the move as reckless.']))