from fastapi import APIRouter

router = APIRouter(prefix='', tags=['ops'])

@router.get('/health')
def health():
    return {'status': 'ok'}

@router.get('/metrics')
def metrics():
    # Minimal; expand with histograms later
    return {'uptime': 'n/a', 'requests': 'n/a'}