import os, uuid
from decimal import Decimal, ROUND_HALF_UP
import structlog

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
SAMPLE_RATE = float(os.getenv('SAMPLE_RATE', '1.0'))

PRICING = {
    'openai:gpt-5-mini': {
        'in': 0.025,
        'in_cached': 0.0025,
        'out': 0.20}
}

def setup_logging():
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt='iso'),
            structlog.processors.JSONRenderer(),
        ]
    )
    return structlog.get_logger()

log = setup_logging()

def new_request_id() -> str:
    return uuid.uuid4().hex

def should_sample() -> bool:
    return SAMPLE_RATE >= 1.0 or (os.urandom(1)[0] / 255.0 < SAMPLE_RATE)

def _as_decimal(x: float) -> Decimal:
    return Decimal(str(x))

def estimate_cost_cents(model_key: str, in_tokens: int, out_tokens: int, cached_in_tokens: int = 0) -> int:
    p = PRICING.get(model_key, {'in': 0.0, 'in_cached': 0.0, 'out': 0.0})
    uncached = max(in_tokens - cached_in_tokens, 0)
    
    cents = (
        _as_decimal(uncached) / Decimal(1000) * _as_decimal(p['in']) + 
        _as_decimal(cached_in_tokens) / Decimal(1000) * _as_decimal(p.get('in_cached', 0.0)) + 
        _as_decimal(out_tokens) / Decimal(1000) * _as_decimal(p['out'])
    )
    if cents == 0:
        return 0
    if cents < 1:
        return 1
    return int(cents.quantize(Decimal('1'), rounding=ROUND_HALF_UP))