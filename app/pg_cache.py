import os, json, datetime
import psycopg
from psycopg_pool import ConnectionPool  # lightweight pool

DATABASE_URL = os.getenv("DATABASE_URL")
POOL = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=5, kwargs={"autocommit": True})

TTL_SECONDS = 260,000

def cache_get(cache_key: str):
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM http_cache WHERE cache_key = %s AND expires_at > NOW()",
                (cache_key,),
            )
            row = cur.fetchone()
            return row[0] if row else None

def cache_set(cache_key: str, payload: dict):
    """Upsert payload with TTL; payload should be JSON-serializable."""
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO http_cache (cache_key, payload, expires_at)
                VALUES (%s, %s, NOW() + (%s || ' seconds')::interval)
                ON CONFLICT (cache_key)
                DO UPDATE SET payload = EXCLUDED.payload,
                              expires_at = EXCLUDED.expires_at,
                              created_at = NOW()
                """,
                (cache_key, json.dumps(payload), TTL_SECONDS),
            )

def cache_prune():
    """Delete expired rows; call occasionally (e.g., on boot)."""
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM http_cache WHERE expires_at <= NOW()")
