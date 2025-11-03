#!/usr/bin/env python3
import os, json
from datasets import load_dataset
from transformers import (AutoTokenizer, AutoModelForSequenceClassification,
                          Trainer, TrainingArguments, DataCollatorWithPadding)
import evaluate
import numpy as np

MODEL_NAME = 'distilbert-base-multilingual-cased'
CKPT_DIR = 'ckpts/distilbert-mc_sent_v4'
os.makedirs(CKPT_DIR, exist_ok=True)

LABEL2ID = {'negative': 0, 'neutral': 1, 'positive': 2}
ID2LABEL = {v: k for k, v in LABEL2ID.items()}

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
metric_f1 = evaluate.load('f1')

def tokenize(ex):
    return tokenizer(ex['text'], truncation=True, max_length=256)

def map_labels(ex):
    ex['labels'] = LABEL2ID[ex['label']]
    return ex

ds_full = load_dataset('json', data_files='models/sentiment/dataset.jsonl')['train']

def prep(split):
    ds = ds_full.filter(lambda ex: ex['split']==split)
    ds = ds.map(map_labels)
    ds = ds.map(tokenize, batched=True)
    ds = ds.remove_columns([c for c in ds.column_names if c in ('label', 'split')])
    return ds

train = prep('train')
val = prep('val')
test = prep('test')

data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=1)
    f1_macro = metric_f1.compute(predictions=preds, references=labels, average='macro')['f1']
    return {'macro_f1': f1_macro}

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME, num_labels=3, id2label=ID2LABEL, label2id=LABEL2ID
)

args = TrainingArguments(
    output_dir=CKPT_DIR,
    learning_rate=3e-5,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    num_train_epochs=2,
    weight_decay=0.01,
    eval_strategy='epoch',
    save_strategy='epoch',
    metric_for_best_model='macro_f1',
    load_best_model_at_end=True,
    seed=42,
    report_to=[]
)

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=train,
    eval_dataset=val,
    compute_metrics=compute_metrics,
    data_collator=data_collator
)

trainer.train()
test_metrics = trainer.evaluate(test)
with open(os.path.join(CKPT_DIR, 'metrics.json'), 'w') as f:
    json.dump(test_metrics, f, indent=2)
    
model.save_pretrained(CKPT_DIR)
tokenizer.save_pretrained(CKPT_DIR)
print('Saved checkpoint to', CKPT_DIR)
print('Test macro-F1:', round(test_metrics['eval_macro_f1'], 4))

