import os, json
try:
    import psycopg
    from psycopg_pool import ConnectionPool
except Exception:
    psycopg = None 

PG_URL = os.getenv("DATABASE_URL")
if not PG_URL:
    raise RuntimeError('DATABASE_URL not set')
POOL = ConnectionPool(conninfo=PG_URL, min_size=1, max_size=5)

TTL_SECONDS = 72 * 3600

def _conn():
    if not PG_URL or not psycopg:
        return None
    return psycopg.connect(PG_URL)

def cache_get(cache_key: str):
    c = _conn()
    if not c:
        return None
    with c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT payload FROM http_cache 
                WHERE cache_key = %s AND expires_at > NOW()
                """,
                (cache_key,),
            )
            row = cur.fetchone()
            return row[0] if row else None

def cache_set(cache_key: str, payload: dict, ttl_seconds: int):
    data = json.dumps(payload, ensure_ascii=False)
    c = _conn()
    if not c:
        return
    with c:
        with c.cursor() as cur:
            cur.execute(
                """
                INSERT INTO http_cache (cache_key, payload, expires_at)
                VALUES (%s, %s, NOW() + (%s * INTERVAL '1 second')
                ON CONFLICT (cache_key)
                DO UPDATE SET payload = EXCLUDED.payload,
                              expires_at = EXCLUDED.expires_at,
                              created_at = NOW()
                """,
                (cache_key, data, TTL_SECONDS),
            )
            

def cache_prune(limit: int = 1000):
    c = _conn()
    if not c:
        return 0
    with c:
        with c.cursor() as cur:
            cur.execute(
                """
                DELETE FROM http_cache 
                WHERE ctid IN (
                    SELECT ctid from http_cache
                    WHERE expires_at <= NOW() 
                    ORDER BY expires_at ASC 
                    LIMIT %s
                )
                """,
                (limit,),
            )
