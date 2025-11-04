#!/usr/bin/env python3
import os, sqlite3

DB = os.getenv('DB_PATH','data/app.db')
DAYS = 30

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("DELETE FROM analyses WHERE create_time < datetime('now', ?)", (f'-{DAYS} days',))
    conn.commit()
    conn.close()
    print(f"Deleted analyses older than {DAYS} days")

if __name__ == '__main__':
    main()
