#!/usr/bin/env python3
import sqlite3, sys
import datetime as dt
import email.utils as eut

DB = 'data/app.db'
COL_PUB = 'pub_time'
COL_CREATE = 'create_time'

def to_iso_utc(s: str) -> str | None:
    if not s or s.strip() == '':
        return None
    try:
        dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
        return s if 'Z' in s or '+' in s else s + '+00:00'
    except Exception:
        pass
    try:
        d = eut.parsedate_to_datetime(s)
        d_utc = d.astimezone(dt.timezone.utc)
        return d_utc.isoformat()
    except Exception:
        return None
    
def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(f"SELECT id, {COL_PUB}, {COL_CREATE} FROM articles")
    rows = cur.fetchall()
        
    cur.execute("BEGIN")
    fixed_pub = fixed_create = 0
    
    for _id, pub, crt in rows:
        new_pub = to_iso_utc(pub) if (pub and pub.endswith(' GMT')) else pub
        new_crt = to_iso_utc(crt) if (crt and crt.endswith(' GMT')) else crt
        
        # normalize empty strings to NULL
        if new_pub == '': new_pub = None
        if new_crt == '': new_crt = None
        
        if new_pub != pub or new_crt != crt:
            cur.execute(
                f"UPDATE articles SET {COL_PUB}=?, {COL_CREATE}=? WHERE id=?",
                (new_pub, new_crt, _id)
            )
            fixed_pub += int(new_pub != pub)
            fixed_create += int(new_crt != crt)
            
    conn.commit()
    conn.close()
    print(f'Updated {fixed_pub} pub_time and {fixed_create} create_time values.')
    
if __name__ =='__main__':
    main()
            