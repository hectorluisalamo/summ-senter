#!/usr/bin/env python3
import duckdb, os
os.makedirs('eval', exist_ok=True)
duck = duckdb.connect('eval/eval.duckdb')

duck.execute("INSTALL sqlite_scanner;")
duck.execute("LOAD sqlite_scanner;")
duck.execute("ATTACH 'data/app.db' AS my_db (TYPE SQLITE);")

duck.execute("""
CREATE OR REPLACE TABLE ingest_articles AS
SELECT
  id, url, domain, title, lang,
  TRY_STRPTIME(CAST(pub_time AS VARCHAR), ['%Y-%m-%dT%H:%M:%S%z','%Y-%m-%dT%H:%M:%S.%f%z']) AS pub_time_ts,
  TRY_STRPTIME(CAST(create_time AS VARCHAR), ['%Y-%m-%dT%H:%M:%S%z','%Y-%m-%dT%H:%M:%S.%f%z']) AS create_time_ts,
  create_time AS create_time_raw,
  snippet, text_hash
FROM my_db.articles;
""")

duck.execute("DETACH my_db;")
duck.execute("COPY ingest_articles TO 'eval/ingest_articles.parquet' (FORMAT PARQUET);")
print('Exported to eval/ingest_articles.parquet')
