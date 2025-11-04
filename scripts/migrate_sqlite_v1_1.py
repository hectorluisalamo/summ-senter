#!/usr/bin/env python3
import sqlite3, os
from pathlib import Path

DB = os.getenv('DB_PATH', 'data/app.db')
SCHEMA_PATH = Path('data/schema_v1_1.sql')

SQL_BACKFILL = """
INSERT OR IGNORE INTO ingest_log (id, url, status, note, create_time)
SELECT hex(randomblob(16)), url, fetch_status, NULL, create_time
FROM articles
WHERE fetch_status IS NOT NULL;
"""

SQL_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_articles_text_hash     ON articles(text_hash);
CREATE INDEX IF NOT EXISTS idx_articles_create_time   ON articles(create_time);
CREATE INDEX IF NOT EXISTS idx_analyses_article_id    ON analyses(article_id);
"""

def col_exists(cur, table, col):
    cur.execute(f'PRAGMA table_info({table})')
    return any(r[1] == col for r in cur.fetchall())

def main():
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute('PRAGMA foreign_keys = OFF;')
        try:
            schema_sql = SCHEMA_PATH.read_text(encoding='utf-8')
            cur.executescript(schema_sql)
            
            if col_exists(cur, 'articles', 'fetch_status'):
                cur.executescript(SQL_BACKFILL)
                try:
                    cur.execute('ALTER TABLE articles DROP COLUMN fetch_status;')
                    print('Dropped fetch_status column from articles table.')
                except sqlite3.OperationalError as e:
                    print(f'Could not drop fetch_status column: {e}')
            
            cur.executescript(SQL_CREATE_INDEXES)
        
        finally:
            cur.execute('PRAGMA foreign_keys = ON;')
            
    print('Migrated to v1.1 succesfully.')
    
if __name__ == '__main__':
    main()