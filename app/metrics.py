import threading
from collections import defaultdict, deque

try:
    from prometheus_client import Counter as _PCounter, Histogram as _PHist, generate_latest, CONTENT_TYPE_LATEST
    PROM = True
    P_COUNT = _PCounter('analyze_requests_total', 'Total analyze requests')
    H_LAT = _PHist('analyze_latency_ms', 'Analyze latency ms', buckets=(100, 250, 500, 1000, 2000, 5000))
except Exception:
    PROM = False
    def generate_latest() -> bytes:
        return b'# prometheus not enabled\n'
    CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4; charset=utf-8'
    class _Noop:
        def inc(self, *a, **k):
            pass
        def observer(self, *a, **k):
            pass
    P_COUNT = _Noop()
    H_LAT = _Noop()

_lock = threading.Lock()
counters = defaultdict(int)
timings_ms = defaultdict(lambda: deque(maxlen=5000))

def inc(name: str, amount: int = 1) -> None:
    with _lock:
        counters[name] += amount
        
def observe_ms(name: str, duration_ms: float) -> None:
    with _lock:
        timings_ms[name].append(duration_ms)

def snapshot_metrics():
    with _lock:
        c = dict(counters)
        t = {k: list(v) for k, v in timings_ms.items()}
    def stats(vals):
        if not vals:
            return {'count': 0, 'p50': 0, 'p95': 0, 'max': 0}
        sorted_vals = sorted(vals)
        count = len(sorted_vals)
        p50 = sorted_vals[int(0.5 * (count - 1))]
        p95 = sorted_vals[int(0.95 * (count - 1))]
        return {'count': count, 'p50': p50, 'p95': p95, 'max': sorted_vals[-1]}
    return {
        'counters': c,
        'timings_ms': {k: stats(v) for k, v in t.items()}
        }