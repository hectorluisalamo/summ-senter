import os, json
try:
    import psycopg
except Exception:
    psycopg = None 

PG_URL = os.getenv("DATABASE_URL")
TTL_SECONDS = 72 * 3600

TABLE = 'http_cache'

def _conn():
    if not PG_URL or not psycopg:
        return None
    return psycopg.connect(PG_URL)

def cache_get(cache_key: str) -> str | None:
    with _conn() as conn, conn.cursor() as cur:
            cur.execute(f"""
                SELECT payload FROM http_cache 
                WHERE cache_key = %s AND expires_at > NOW()
            """, (cache_key,))
            row = cur.fetchone()
            return row[0] if row else None

def cache_set(cache_key: str, payload: str, ttl_s: int = TTL_SECONDS) -> None:
    with _conn() as conn, conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO http_cache (cache_key, payload, expires_at)
                VALUES (%s, %s, NOW() + make_interval(secs => %s))
                ON CONFLICT (cache_key)
                DO UPDATE SET payload = EXCLUDED.payload,
                              expires_at = EXCLUDED.expires_at,
                              created_at = NOW()
            """, (cache_key, payload, str(TTL_SECONDS)))
            conn.commit()

def cache_prune(limit: int = 1000):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(f"""
            DELETE FROM http_cache 
            WHERE ctid IN (
            SELECT ctid from http_cache
            WHERE expires_at <= NOW() 
            ORDER BY expires_at ASC 
            LIMIT %s)
        """, (limit,))
        conn.commit()

def cache_delete(key: str):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(f"DELETE FROM {TABLE} WHERE cache_key = %s", (key,))
        conn.commit()