from fastapi import APIRouter, HTTPException
import os, sqlite3

router = APIRouter(prefix='/{article}', tags=['articles'])

DB_PATH = os.getenv('DB_PATH', 'data/app.db')

@router.get('/{aid}')
def get_article(aid: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone()
    if not row:
        raise HTTPException(404, "not_found")
    outs = conn.execute("SELECT summary, sentiment, confidence, cost_cents, model_version, create_time FROM analyses WHERE article_id=?", (aid,)).fetchall()
    conn.close()
    return {'article': dict(row), 'analyses': [dict(o) for o in outs]}