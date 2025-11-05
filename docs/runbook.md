What: Slow/costly /analyze requests.

How to trace:
1) Reproduce and grab "request_id" from logs.
2) Search logs for `{"event":"analyze", "request_id":"<id>"}`.
3) Compare `latency_ms` vs `sum_latency_ms`: if sum ≪ total → network/fetch is slow.
4) If `cache_hit=false` repeatedly for same URL → check Redis URL + key versioning.
5) If cost spikes → verify token usage & pricing map in app/obs.py.

Mitigations:
- Raise CACHE_TTL or add missing domain to allowlist to avoid refetch churn.
- Tune summarizer max_tokens; lower temperature to reduce rambling.
- Block gnarly domains in allowlist temporarily.
