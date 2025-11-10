#!/usr/bin/env python3
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import os, torch

MODEL_LOCAL = os.getenv('TRANSLATE_LOCAL_MODEL', '/app/ckpts/opus-mt-es-en')
MODEL_NAME = os.getenv('TRANSLATE_MODEL', 'Helsinki-NLP/opus-mt-es-en')

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model.to(device).eval()

def _lazy_init():
    global tokenizer, model
    if tokenizer is None or model is None:
        try:
            tokenizer = AutoTokenizer.from_pretrained(MODEL_LOCAL)
            model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_LOCAL)
        except Exception:
            # fallback to remote (should be rare once baked)
            tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
        model.to(device).eval()

def translate_es_to_en(text: str, max_input_tokens: int = 512, max_new_tokens: int = 128) -> str:
    text = ' '.join((text or '').split())
    max_input_tokens = min(max_input_tokens, tokenizer.model_max_length)
    enc = tokenizer([text], return_tensors='pt', truncation=True, max_length=max_input_tokens, padding=False)
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.inference_mode():
        out = model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            num_beams=4,
            length_penalty=1.0,
            use_cache=True
        )
    return tokenizer.decode(out[0], skip_special_tokens=True)