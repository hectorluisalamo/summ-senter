import threading
from collections import defaultdict, deque

_lock = threading.Lock()
counters = defaultdict(int)
timings_ms = defaultdict(list, lambda: deque(maxlen=5000))

def inc(name: str, amount: int = 1) -> None:
    """Increment a counter by amount."""
    with _lock:
        counters[name] += amount
        
def observe_ms(name: str, duration_ms: float) -> None:
    """Record latency (milliseconds) for `name`."""
    with _lock:
        timings_ms[name].append(duration_ms)

def snapshot_metrics():
    """Returns a snapshot of current metrics."""
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