from fastapi import APIRouter, HTTPException, Response
from app.metrics import snapshot_metrics
from app.metrics import PROM, generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(prefix='', tags=['ops'])

@router.get('/health')
def health():
    return {'status': 'ok'}

@router.get('/metrics')
def metrics():
    return snapshot_metrics()

@router.get('/metrics.prom')
def metrics_prom():
    if not PROM:
        raise HTTPException(status_code=501, detail='Prometheus not enabled')
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)