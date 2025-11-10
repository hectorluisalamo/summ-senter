import os
try:
    import redis as _redis
    from redis.exceptions import RedisError
except Exception:
    _redis = None
    class RedisError(Exception):
        pass

def get_client(url: str):
    if not url or not _redis:
        return None
    return _redis.from_url(url)