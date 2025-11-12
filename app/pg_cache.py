import os, json
import psycopg
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL not set')
POOL = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=5)

TTL_SECONDS = 72 * 3600
MAX_PAYLOAD_BYTES = 500,000

def _conn_autocommit(conn: psycopg.Connection):
    if not conn.autocommit:
        conn.autocommit = True
    return conn

def cache_get(cache_key: str):
    with POOL.connection() as conn:
        conn = _conn_autocommit(conn)
        with conn.cursor() as cur:
            cur.execute(
                """"
                SELECT payload FROM http_cache 
                WHERE cache_key = %s AND expires_at > NOW()
                """,
                (cache_key,),
            )
            row = cur.fetchone()
            return row[0] if row else None

def cache_set(cache_key: str, payload: dict):
    data = json.dumps(payload, ensure_ascii=False)
    if len(data.encode('utf-8')) > MAX_PAYLOAD_BYTES:
        return
    with POOL.connection() as conn:
        conn = _conn_autocommit(conn)
        with conn.cursor() as cur:
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
    with POOL.connection() as conn:
        conn = _conn_autocommit(conn)
        with conn.cursor() as cur:
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
