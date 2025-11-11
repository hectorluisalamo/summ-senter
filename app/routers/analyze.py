import os, time, hashlib, json
from app.cache import get_client, RedisError
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from urllib.parse import urlparse
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.services import fetch_url, clean_html_to_text, store_analysis, ensure_db
from app.obs import estimate_cost_cents, should_sample, log
from app.metrics import observe_ms, inc

PROVIDER = os.getenv('SUMMARY_PROVIDER,' 'openai')

if PROVIDER == 'stub':
    from tests.conftest import mock_summarize, mock_sentiment
else:
    from scripts.summarize_openai import summarize
    from scripts.sentiment_infer import predict_label
try:
    from app.metrics import PROM, P_COUNT, H_LAT
except Exception:
    PROM, P_COUNT, H_LAT = False, None, None

MAX_INPUT_CHARS = 8000
CACHE_TTL_S = 259200
REDIS_URL = os.getenv('REDIS_URL', '')
API_SCHEMA_VER = 'v1.1'

router = APIRouter(prefix='/analyze', tags=['analyze'])
    
rds = get_client(REDIS_URL)

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

def _as_str(x, default=''):
    if isinstance(x, (list, tuple)):
        return str(x[0]) if x else default
    return str(x) if x is not None else default

@router.post('/', response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, request: Request):
    ensure_db()
    start = time.time()
    if sum([bool(req.url), bool(req.html), bool(req.text)]) != 1:
        raise HTTPException(status_code=400, detail='provide exactly one of url|html|text')
    
    lang = _as_str(req.lang or 'en').lower()
    url = _as_str(req.url)
    domain, title, meta = 'local', None, {}
    
    if req.url:
        text = fetch_url(url, timeout_s=20)
        domain = urlparse(str(req.url)).netloc
    elif req.html:
        text = clean_html_to_text(req.html)
        domain, title = 'local', None
    else:
        text = _as_str(req.text)
        text = ' '.join((text).split())[:MAX_INPUT_CHARS]
        domain, title = 'local', None
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=400, detail='empty_text')
    
    # Cache check
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
            total_latency = int((time.time() - start) * 1000)
            # Prometheus bump for cache hit
            if PROM:
                P_COUNT.inc()
                H_LAT.observe(total_latency)
                
            return payload
        
    # Summarize
    sum_out = summarize(text, lang)
    summary = sum_out['summary']
    
    if summary == '':
        summary = 'EMPTY_FROM_MODEL'
        
    sum_latency = sum_out['latency_ms']
    
    # Sentiment on summary
    try:
        text_for_sent = summary or text
        label, conf, mv_sent = predict_label(text_for_sent)
    except Exception as e:
        log.info('Sentiment_error_debug', type=str(type(summary)), preview=str(summary)[:120])
        raise HTTPException(status_code=502, detail=f'sentiment_error: {e}')
    
    model_version = f"{sum_out['model_version']}|sent:{mv_sent}"
    
    # Token usage + cost
    usage = sum_out.get('usage') or {}
    try:
        in_tokens = int(usage.get('prompt_tokens', 0))
        out_tokens = int(usage.get('completion_tokens', 0))
    except (ValueError, TypeError):
        in_tokens, out_tokens = 0, 0
    tokens_used = in_tokens + out_tokens
    cached_in_tokens = 0
    model_key = sum_out['model_version'].split('@')[0]
    cost_cents = estimate_cost_cents(model_key, in_tokens, out_tokens, cached_in_tokens)
    
    # Metrics + logs
    total_latency = int((time.time() - start) * 1000)
    observe_ms('analyze_latency_ms', total_latency)
    inc('analyze_requests_total', 1)
    cache_hit = False
    
    rid = getattr(getattr(request, 'state', object()), 'request_id', None)
        
    if should_sample():
        log.info(
                'analyze',
                 request_id=request.state.request_id,
                 url=str(req.url) if req.url else None,
                 domain=domain,
                 lang=lang,
                 model_version=model_version,
                 cache_hit=cache_hit,
                 latency_ms=total_latency,
                 sum_latency_ms=sum_latency,
                 cost_cents=cost_cents,
                 in_tokens=in_tokens,
                 out_tokens=out_tokens
        )
    
    # Assemble resonse
    aid = str(uuid4())
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
        'cache_hit': cache_hit,
        'used_fallback': not sum_out['model_version'].startswith('openai:')
    }
    
    # Store & cache
    should_cache = not sum_out['model_version'].startswith('rule:')
    store_analysis(
        aid, 
        str(req.url) if req.url else '', 
        domain, 
        title, 
        lang,
        summary, 
        label, 
        conf, 
        resp['tokens'], 
        total_latency, 
        cost_cents, 
        model_version)
    if rds and should_cache:
        cache_setex(ckey, CACHE_TTL_S, json.dumps(resp))
        
    total_latency = int((time.time() - start) * 1000)
    resp['latency_ms'] = total_latency
    
    # Prometheus bump for non-cache path
    if PROM:
        P_COUNT.inc()
        H_LAT.observe(total_latency)
        
    return resp

@router.post('', response_model=AnalyzeResponse)
def analyze_noslash(req: AnalyzeRequest, request: Request):
    return analyze(req, request)