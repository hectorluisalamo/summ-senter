import os, time, uuid
import structlog

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
SAMPLE_RATE = float(os.getenv('SAMPLE_RATE', '1.0'))

P_IN = float(os.getenv('PRICE_CENTS_IN_GPT5_MINI', '0.00025'))  # Cents per 1K tokens (0.25 per 1M)
P_OUT = float(os.getenv('PRICE_CENTS_OUT_GPT5_MINI', '0.002'))   # Cents per 1K tokens (2.0 per 1M)

PRICING = {
    'openai:gpt-5-mini': {'in': P_IN, 'out': P_OUT}
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

def estimate_cost_cents(model_version: str, in_tokens: int, out_tokens: int) -> int:
    key = model_version.split('@')[0]
    p = PRICING.get(key, {'in': 0.0, 'out': 0.0})
    cents = (in_tokens / 1000) * p['in'] + (out_tokens / 1000) * p['out']
    return int(round(cents))