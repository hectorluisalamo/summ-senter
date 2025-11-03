#!/usr/bin/env python3
import os, subprocess, sys

ENGINE = os.getenv('DB_ENGINE', 'sqlite')
SQLITE_DB = os.getenv('DB_PATH', 'data/app.db')
PG_URL = os.getenv('DB_URL', 'postgresql://news_summ_sent_user:ac4DEq6GQ21xk1HYGFdxobb2IW8fkvqs@dpg-d43p6ler433s739nl3vg-a/news_summ_sent')

def main():
    if ENGINE == 'sqlite':
        print('Running SQLite migration -> v1.1')
        rc = subprocess.call([sys.executable, 'scripts/migrate_sqlite_v1_1.py'])
        sys.exit(rc)
    elif ENGINE == 'postgres':
        print('Apply schema_v1_1_postgres.sql to DATABASE_URL')
        print('Example psql command:')
        print(f'psql "{PG_URL}" -f data/schema_v1_1_postgres.sql')
        db_url = PG_URL
    else:
        print(f'Unkown DB_ENGINE. Use sqlite or posttgres.')
        sys.exit(1)

if __name__ == '__main__':
    main()