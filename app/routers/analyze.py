import os, re, time, hashlib, json
from app.cache import get_client, RedisError
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from urllib.parse import urlparse
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.services import fetch_url, clean_article_html, store_analysis, ensure_db, build_text_hash, build_snippet, maybe_extract_pub_time
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
FETCH_TIMEOUT_S = 20

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

def top_sentences(text: str, n: int = 3):
    sents = re.split(r'(?<=[.!?])\s+', (text or '').strip())
    return [s for s in sents[:n] if s]

@router.post('/', response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, request: Request):
    ensure_db()
    start = time.time()
    if sum([bool(req.url), bool(req.html), bool(req.text)]) != 1:
        raise HTTPException(status_code=400, detail='provide exactly one of url|html|text')
    
    lang = _as_str(req.lang or 'en').lower()
    domain, title, meta = 'local', None, {}
    
    if req.url:
        url = _as_str(req.url)
        html = fetch_url(url, timeout_s=FETCH_TIMEOUT_S)
        domain = urlparse(url).netloc.lower() or 'local'
        text, meta = clean_article_html(html)
        title = meta.get('title')
        pub_time = meta.get('pub_time') if isinstance(meta, dict) else None
        if not pub_time:
            pub_time = maybe_extract_pub_time(html)
    elif req.html:
        text, meta = clean_article_html(req.html)
        title = meta.get('title')
        pub_time = meta.get('pub_time') if isinstance(meta, dict) else None
        if not pub_time:
            pub_time = maybe_extract_pub_time(req.html)
        domain = 'local'
    else:
        text = _as_str(req.text)
        text = ' '.join((text).split())[:MAX_INPUT_CHARS]
        domain, title, pub_time, meta = 'local', None, None, {'source': 'direct'}
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=400, detail='empty_text')
    
    snippet = meta.get('snippet') or build_snippet(text)
    text = _as_str(text)
    text_hash = build_text_hash(text)
    
    # Cache check
    mv_sum = 'openai:gpt-5-mini@sum_v1'
    mv_sent = 'distilbert-mc@sent_v4'
    mv_trans = 'opus-mt-es-en@v1' if lang == 'es' else 'None'
    
    content_id = text_hash 
    
    ck_blob = '|'.join([
        API_SCHEMA_VER,
        content_id,
        lang,
        mv_sum,
        mv_sent,
        mv_trans,
    ])
    ckey = 'an:' + hashlib.sha256(ck_blob.encode('utf-8')).hexdigest()
    
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
    try:
        in_tokens = int(sum_out['usage']['prompt_tokens'], 0)
        out_tokens = int(sum_out['usage']['completion_tokens'], 0)
    except (ValueError, TypeError):
        in_tokens, out_tokens = 0, 0
    tokens_used = in_tokens + out_tokens
    cached_in_tokens = 0
    model_key = sum_out['model_version'].split('@')[0]
    cost_cents = estimate_cost_cents(model_key, in_tokens, out_tokens, cached_in_tokens)
    
    log.info('sum_types', summary_t=type(summary).__name__, in_t=in_tokens, out_t=out_tokens)
    if not isinstance(summary, str):
        raise HTTPException(500, detail={'code': 'summary_not_str' ,'message': str(type(summary))})
    
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
        'sentiment': label,
        'confidence': conf,
        'tokens': tokens_used,
        'latency_ms': total_latency,
        'costs_cents': cost_cents,
        'model_version': model_version,
        'cache_hit': cache_hit,
        'key_sentences': top_sentences(summary, 3),
        'used_fallback': not sum_out['model_version'].startswith('openai:')
    }
    
    # Store & cache
    should_cache = not sum_out['model_version'].startswith('rule:')
    log.info('db_bind_types', title_t=type(title).__name__, snippet_t=type(snippet).__name__, text_t=type(text).__name__)
    store_analysis(
        aid, 
        url, 
        domain, 
        title, 
        lang,
        pub_time,
        snippet,
        text_hash,
        summary, 
        label, 
        conf,  
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