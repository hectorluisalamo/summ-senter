#!/usr/bin/env python3
import time
from typing import Dict
from scripts.summarize_openai import call_openai, build_prompt
from scripts.translate_es_to_en import translate_es_to_en

# Optional local fallback (lazy import)
def _try_local_t5(text: str, max_new_tokens: int = 160):
    try:
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        import torch
        tokenizer = AutoTokenizer.from_pretrained('t5-small')
        model = AutoModelForSeq2SeqLM.from_pretrained('t5-small').eval()
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model.to(device)
        batch = tokenizer('summarize: ' + text, return_tensors='pt', truncation=True, max_length=1024)
        with torch.inference_mode():
            out = model.generate(**{k: v.to(device) for k, v in batch.items()}, max_new_tokens=max_new_tokens)
        return tokenizer.decode(out[0], skip_special_tokens=True)
    except Exception as e:
        return None

def _lead3(text: str, n: int = 3, max_words: int = 180) -> str:
    import re
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    take = sents[:n]
    words = []
    for s in take:
        for w in s.split():
            if len(words) < max_words:
                words.append(w)
    return '' ''.join(words)

def summarize_with_fallback(raw_text: str, lang: str) -> Dict:
    text = raw_text
    if lang == 'es':
        text = translate_es_to_en(text)

    # 1) API path
    p = build_prompt(text)
    t0 = time.time()
    try:
        out = call_openai(p) # may raise (429, network, etc.)
        return {
            'summary': out,
            'latency_ms': int((time.time() - t0) * 1000),
            'model_version': 'openai:gpt-5-mini@sum_v1'
        }
    except Exception as e_api:
        api_err = str(e_api)

    # 2) Local T5 fallback
    t1 = time.time()
    local = _try_local_t5(text)
    if local:
        return {
            'summary': local,
            'latency_ms': int((time.time() - t1) * 1000),
            'model_version': 'hf:t5-small@sum_fb1'
        }

    # 3) Lead-3 fallback
    t2 = time.time()
    lead = _lead3(text)
    return {
        'summary': lead,
        'latency_ms': int((time.time() - t2) * 1000),
        'model_version': 'rule:lead3@sum_fb2'
    }
