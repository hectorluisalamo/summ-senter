import os, time, uuid, hashlib, json
from fastapi import APIRouter, HTTPException
from urllib.parse import urlparse
import redis
from redis.exceptions import RedisError
from app.schemas import AnalyzeRequest, AnalyzeResponse
from scripts.summarize_orchestrator import summarize_with_fallback
from scripts.sentiment_infer import predict_label
from app.services import fetch_url, clean_html_to_text, store_analysis, ensure_db

MAX_INPUT_CHARS = 8000
CACHE_TTL_S = 259200
REDIS_URL = os.getenv('REDIS_URL', '')
API_SCHEMA_VER = 'v1.1'

router = APIRouter(prefix='/analyze', tags=['analyze'])

rds = redis.from_url(REDIS_URL) if REDIS_URL else None

def cache_get(key: str):
    if not rds:
        return None
    try:
        return rds.get(key)
    except RedisError:
        return None
    
def cache_setex(key: str, ttl: int, val: str):
    if not rds:
        return
    try:
        rds.setex(key, ttl, val)
    except RedisError:
        return

@router.post('/', response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    ensure_db()
    start = time.time()
    # input source
    if sum([bool(req.url), bool(req.html), bool(req.text)]) != 1:
        raise Exception(400, 'provide exactly one of url|html|text')
    lang = req.lang or 'en'
    # get text
    if req.url:
        text = fetch_url(str(req.url))
        title = None
        domain = urlparse(str(req.url)).netloc
    elif req.html:
        text = clean_html_to_text(req.html)
        domain, title = 'local', None
    else:
        text = ' '.join((req.text or '').split())[:MAX_INPUT_CHARS]
        domain, title = 'local', None
    if not text:
        raise Exception(400, 'empty_text')
    
    # cache check
    mv_sum = 'openai:gpt-5-mini@sum_v1'
    mv_sent = 'distilbert-mc@sent_v4'
    ck_blob = (
        API_SCHEMA_VER + '|' +
        (str(req.url) if req.url else hashlib.sha256(text.encode()).hexdigest()) + '|' + 
        mv_sum + '|' + mv_sent
    )
    ckey = 'an:' + hashlib.sha256(ck_blob.encode()).hexdigest()
    
    if rds:
        hit = cache_get(ckey)
        if hit:
            payload = json.loads(hit)
            if 'costs_cents' not in payload and 'cost_cents' in payload:
                payload['costs_cents'] = payload.pop('cost_cents')
            payload['cache_hit'] = True
            return payload
        
    # summarize
    sum_out = summarize_with_fallback(text, lang)
    summary = sum_out['summary']
    sum_latency = sum_out['latency_ms']
    
    # sentiment on summary
    try:
        label, conf, mv_sent = predict_label(summary)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'sentiment_error: {e}')
    
    # assemble resonse
    aid = str(uuid.uuid4())
    model_version = f'{sum_out['model_version']}|sent:{mv_sent}'
    total_latency = int((time.time() - start) * 1000)
    tokens_used = 0
    cost_cents = 0
    resp = {
        'id': aid,
        'summary': summary,
        'key_sentences': [],
        'sentiment': label,
        'confidence': conf,
        'tokens': tokens_used,
        'latency_ms': total_latency,
        'costs_cents': cost_cents,
        'model_version': model_version,
        'cache_hit': False
    }
    
    # store & cache
    should_cache = not sum_out['model_version'].startswith('rule:')
    store_analysis(aid, str(req.url) if req.url else '', domain, title, lang,
                   summary, label, conf, tokens_used, total_latency, cost_cents, model_version)
    if rds and should_cache:
        cache_setex(ckey, CACHE_TTL_S, json.dumps(resp))
    resp['used_fallback'] = not sum_out['model_version'].startswith('openai:')
    return resp