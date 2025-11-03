import os, redis, traceback, logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routers.analyze import router as analyze_router
from app.routers.articles import router as articles_router
from app.routers.ops import router as ops_router

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

rds = redis.from_url(REDIS_URL) if REDIS_URL else None

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
    # add a table later
    return {'ok': True}

app.include_router(analyze_router)
app.include_router(articles_router)
app.include_router(ops_router)