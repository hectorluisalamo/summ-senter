import os, traceback, logging, time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routers.analyze import router as analyze_router
from app.routers.articles import router as articles_router
from app.routers.ops import router as ops_router
from app.obs import log, new_request_id, should_sample
from app.metrics import observe_ms

logging.basicConfig(level=logging.INFO)

LOG_PATH = 'data/service.log'

ALLOWLIST_PATH = 'config/allowlist.txt'
CACHE_TTL_SECONDS = 259200
REDIS_URL = os.getenv('REDIS_URL', '')
MAX_INPUT_CHARS = 8000
FETCH_TIMEOUT_S = 10
SUM_TIMEOUT_S = 20

app = FastAPI(title='News Summarizer + Sentiment')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

try:
    import redis as _redis
except Exception:
    _redis = None
    
rds = _redis.from_url(REDIS_URL) if (_redis and REDIS_URL) else None

@app.middleware('http')
async def add_request_context(request: Request, call_next):
    rid = new_request_id()
    request.state.request_id = rid
    start = time.time()
    try:
        response = await call_next(request)
        return response
    finally:
        dt = int((time.time() - start) * 1000)
        observe_ms('http_request_ms', dt)
        if should_sample():
            log.info('http_request', rid=rid, path=request.url.path, ms=dt, method=request.method)
    

@app.exception_handler(Exception)
async def all_errors(request: Request, exc: Exception):
    tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, 'a') as fh:
            fh.write(tb + '\n')
    except Exception:
        pass
    return JSONResponse(status_code=500, content={'code': 'internal_error', 'message': str(exc)})

@app.post('/feedback')
def feedback(payload: dict):
    # Add a table later
    return {'ok': True}

app.include_router(analyze_router)
app.include_router(articles_router)
app.include_router(ops_router)