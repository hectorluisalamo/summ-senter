import json, os, re, time, hashlib
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.services import fetch_url, clean_article_html, store_analysis, ensure_db, build_text_hash, build_snippet, maybe_extract_pub_time
from app.obs import estimate_cost_cents, should_sample, log
from app.metrics import observe_ms, inc
from app.pg_cache import cache_get, cache_set, cache_prune, cache_delete


PROVIDER = os.getenv('SUMMARY_PROVIDER,' 'openai')
PG_URL = os.getenv('DATABASE_URL')

PG_CACHE_ENABLED = bool(os.getenv('DATABASE_URL'))

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
API_SCHEMA_VER = 'v1.1'
FETCH_TIMEOUT_S = 20

router = APIRouter(prefix='/analyze', tags=['analyze'])

try:
    cache_prune()
except Exception:
    pass

def normalize_url(url: str) -> str:
    u = urlparse(url)
    host = u.netloc.lower()
    q = [(k, v) for (k, v) in parse_qsl(u.query, keep_blank_values=True) if not k.lower().startswith('utm_')]
    path = u.path.rstrip('/') or '/'
    norm_u = urlunparse((u.scheme or 'https', host, path, '', urlencode(q, doseq=True), ''))
    return norm_u

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
    source_url = ''
    domain, title, meta = 'local', None, {}
    
    if req.url:
        source_url = normalize_url(_as_str(req.url))
        html = fetch_url(source_url, timeout_s=FETCH_TIMEOUT_S)
        domain = urlparse(source_url).netloc.lower() or 'local'
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
    ck_blob = (source_url if source_url else hashlib.sha256(text.encode()).hexdigest()) + '|' + mv_sum + '|' + mv_sent
    ckey = 'an:' + hashlib.sha256(ck_blob.encode()).hexdigest()

    if PG_CACHE_ENABLED:
        cached = cache_get(ckey)
        if cached:
            try:
                payload = json.loads(cached)
            except Exception:
                cache_delete(ckey)
            total_latency = int((time.time() - start) * 1000)
            payload['cache_hit'] = True
            payload['latency_ms'] = total_latency
            payload.get('analysis_latency_ms', payload['latency_ms'])
            observe_ms('analyze_latency_ms', total_latency)
            inc('analyze_requests_total', 1)
            if should_sample():
                log.info('analyze', cache_hit=True, latency_ms=total_latency, model_version=payload.get('model_version'))
            return payload
        
    # Summarize
    sum_out = summarize(text, lang)
    summary = sum_out['summary']
    sum_latency = sum_out['latency_ms']
    
    # Sentiment on summary
    try:
        text_for_sent = snippet or text
        label, conf, mv_sent = predict_label(text_for_sent)
    except Exception as e:
        log.info('Sentiment_error_debug', type=str(type(summary)), preview=str(summary)[:120])
        raise HTTPException(status_code=502, detail=f'sentiment_error: {e}')
    
    model_version = f"{sum_out['model_version']}|sent:{mv_sent}"
    
    # Token usage + cost
    try:
        in_tokens = sum_out['usage']['prompt_tokens']
        out_tokens = sum_out['usage']['completion_tokens']
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
    analysis_latency_ms = sum_latency + 0
    
    # Assemble resonse
    aid = str(uuid4())
    resp = {
        'id': aid,
        'summary': summary,
        'sentiment': label,
        'confidence': conf,
        'tokens': tokens_used,
        'latency_ms': total_latency,
        'analysis_latency_ms': analysis_latency_ms,
        'costs_cents': cost_cents,
        'model_version': model_version,
        'cache_hit': cache_hit,
        'key_sentences': top_sentences(summary, 3)
    }
    
    # Store & cache
    observe_ms('analyze_latency_ms', total_latency)
    inc('analyze_requests_total', 1)
    
    if PG_CACHE_ENABLED:
        cache_copy = dict(resp)
        cache_copy['latency_ms'] = cache_copy.get('analysis_latency_ms', total_latency)
        cache_set(ckey, json.dumps(cache_copy, ensure_ascii=False), CACHE_TTL_S)
    
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
    
    log.info('db_bind_types', title_t=type(title).__name__, snippet_t=type(snippet).__name__, text_t=type(text).__name__)
    store_analysis(
        aid, 
        source_url, 
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
    
    # Prometheus bump for non-cache path
    if PROM:
        P_COUNT.inc()
        H_LAT.observe(total_latency)
        
    return resp

@router.post('', response_model=AnalyzeResponse)
def analyze_noslash(req: AnalyzeRequest, request: Request):
    return analyze(req, request)